import frappe
import requests

def send_fcm_message(doc, method):
    """
    Send message to Firebase when status is "NEW".
    """
    # Verify if the status is "NEW"
    if doc.status != "NEW":
        return

    # Get the Firebase authentication token
    fcm_server_key = frappe.db.get_single_value("FCM Notification Settings", "server_key")
    if not fcm_server_key:
        frappe.throw("Firebase Server key not configured in FCM Settings.")

    # Dados para envio
    headers = {
        "Authorization": f"key={fcm_server_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "notification": {
            "title": doc.subject,
            "body": doc.message
        },
        "priority": "high",
        "to": "/topics/all" if doc.all_users else get_user_fcm_token(doc.user)
    }

    # POST request response
    response = requests.post("https://fcm.googleapis.com/fcm/send", json=payload, headers=headers)

    # Validate response
    if response.status_code == 200:
        frappe.db.set_value("FCM Notification", doc.name, "status", "SENT")
        frappe.db.commit()
    else:
        frappe.log_error(
            f"Error sending FCM message: {response.status_code} - {response.text}",
            "FCM Notification"
        )

def get_user_fcm_token(user):
    """
    Get the token FCM of a specific user.
    """
    token = frappe.db.get_value("User Device", user, "fcm_token")
    if not token:
        frappe.throw(f"User {user} does not have a configured FCM Token.")
    return token