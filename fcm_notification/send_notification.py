import frappe
import requests
import json
import time
from google.oauth2 import service_account
from google.auth.transport.requests import Request

def send_fcm_message(doc, method):
    """
    Send a message to Firebase when the status is "NEW".
    """
    # Verify if the status is "NEW"
    if doc.status != "NEW":
        return

    # Verify if the user has a configured FCM Token
    if not doc.all_users and not frappe.db.get_value("User Device", doc.user, "device_token"):
        print("DEBUG: User does not have a configured FCM Token, exiting...")
        return

    # Get the path to the service account JSON file
    service_account_json = frappe.db.get_single_value("FCM Notification Settings", "server_key")
    if not service_account_json:
        frappe.throw("The service account JSON content is not configured in FCM Notification Settings.")

    # Load the service account credentials
    try:
        service_account_info = json.loads(service_account_json)
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=["https://www.googleapis.com/auth/firebase.messaging"]
        )
    except Exception as e:
        frappe.throw(f"Error loading service account credentials: {e}")

    # Get the OAuth 2.0 access token
    try:
        credentials.refresh(Request())
        access_token = credentials.token
    except Exception as e:
        frappe.throw(f"Error getting OAuth 2.0 access token: {e}")

    users_to_notify = []
    if doc.all_users:
        for user in frappe.get_all("User Device", fields=['device_token']):
            users_to_notify.append(user.device_token)
    else:
        users_to_notify.append(get_user_fcm_token(doc.user))

    frappe.log_error(f"DEBUG: Users to notify({len(users_to_notify)}): {users_to_notify}", "FCM Notification")

    for token_to_notify in users_to_notify:
        # Build the message payload
        message = {
            "message": {
                "notification": {
                    "title": doc.subject,
                    "body": doc.message
                },
                "token": token_to_notify,
                "topic": None
            }
        }

        # Remove keys with None value
        message["message"] = {k: v for k, v in message["message"].items() if v is not None}

        # Endpoint API HTTP v1
        project_id = credentials.project_id
        url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; UTF-8",
        }

        response = requests.post(url, headers=headers, data=json.dumps(message))

        # Validate the response
        if response.status_code == 200:
            frappe.db.set_value("FCM Notification", doc.name, "status", "SENT")
            frappe.db.commit()
        else:
            print(f"Error sending FCM message: {response.status_code} - {response.text}")
            frappe.log_error(
                f"Error sending FCM message: {response.status_code} - {response.text}",
                "FCM Notification"
            )

def get_user_fcm_token(user):
    """
    Get the FCM token from the User Device doctype.
    """
    return frappe.db.get_value("User Device", user, "device_token")

def notification_handler(doc, method):
    """
    Handle the notification before validation and create FCM notification based on conditions.
    """
    if doc.channel != "FCM":
        return

    # Verify if the notification is enabled
    if not doc.enabled:
        return

    if not doc.document_type:
        frappe.throw("Document Type is required for FCM notifications")

def process_document_for_fcm(doc, method):
    """
    This function should be called when a monitored document is modified
    """
    print(f"DEBUG: Process document for FCM called -> {doc}")
    # Search for all active FCM notifications for this document type
    notifications = frappe.get_all(
        "Notification",
        filters={
            "enabled": 1,
            "channel": "FCM",
            "document_type": doc.doctype
        },
        fields=["*"]
    )

    # If there are no notifications, return
    if not notifications:
        print("DEBUG: No notifications found, exiting...")
        return

    print(f"DEBUG: Notifications: {notifications}")

    for notification in notifications:
        try:
            # Check the condition for the current document
            print(f"DEBUG: Condition: {notification.condition}")
            if notification.condition:
                context = {"doc": doc}
                if not eval(notification.condition, context):
                    continue

            print("DEBUG: Condition ok")

            # Process the message template
            subject = frappe.render_template(
                notification.subject or notification.message_title or f"Document: {doc}",
                context
            )
            message = frappe.render_template(notification.message, context)

            print(f"DEBUG: Subject: {subject}")
            print(f"DEBUG: Message: {message}")

            # Determine recipients
            # if doctype is HD Ticket, get users from agent_group field
            if doc.doctype == "HD Ticket":
                recp = {}
                doc_hd_ticket = frappe.get_doc("HD Ticket", doc.name)
                hd_team = frappe.get_doc("HD Team", doc_hd_ticket.agent_group)
                if hd_team.get('users'):
                    recp['recipients'] = [{'owner': i.get('user')} for i in hd_team.get('users')]
            else:
                recp = frappe.get_doc("Notification", notification.name, fields=['recipients']).as_dict()
            print(f"DEBUG: Recipients: {recp.get('recipients')}")
            if recp.get('recipients'):
                for recipient_array in recp.get('recipients'):
                    # Get device from User
                    user_device = frappe.get_value("User Device", {'user': recipient_array.get('owner')}, 'name')
                    # Create FCM notification for each recipient
                    if user_device:
                        create_fcm_notification(subject, message, user_device, False, doc)
                        print(f"DEBUG: Create FCM notification for recipient: {recipient_array.get('owner')}")
            else:
                # Create FCM notification for all users
                create_fcm_notification(subject, message, None, True, doc)
                print("DEBUG: Create FCM notification for all users")  

        except Exception as e:
            frappe.log_error(
                f"Error processing FCM notification {notification.name} for document {doc.name}: {str(e)}",
                "FCM Notification Error"
            )

def create_fcm_notification(subject, message, user=None, all_users=False, reference_doc=None):
    """
    Create FCM notification document
    """
    print("DEBUG: Create FCM notification called")
    fcm_notification = frappe.get_doc({
        "doctype": "FCM Notification",
        "subject": subject,
        "message": message,
        "user": user,
        "all_users": all_users,
        "status": "NEW",
        "reference_doctype": reference_doc.doctype if reference_doc else None,
        "reference_name": reference_doc.name if reference_doc else None
    })
    
    fcm_notification.insert(ignore_permissions=True)
    frappe.db.commit()
