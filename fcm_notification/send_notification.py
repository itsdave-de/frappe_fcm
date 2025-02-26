import frappe
import requests
import json
from google.oauth2 import service_account
from google.auth.transport.requests import Request

def send_fcm_message(doc, method):
    """
    Send a message to Firebase when the status is "NEW".
    """
    # Verify if the status is "NEW"
    if doc.status != "NEW":
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
        frappe.throw(f"Erro ao obter o token de acesso OAuth 2.0: {e}")

    # Build the message payload
    message = {
        "message": {
            "notification": {
                "title": doc.subject,
                "body": doc.message
            },
            "token": get_user_fcm_token(doc.user) if not doc.all_users else None,
            "topic": "all" if doc.all_users else None
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
    token = frappe.db.get_value("User Device", user, "device_token")
    if not token:
        frappe.throw(f"User {user} does not have a configured FCM Token.")
    return token

def notification_handler(doc, method):
    """
    Handle the notification before validation.
    """
    print("DEBUG: Call the send_fcm_message function")
    print(doc)
    return
