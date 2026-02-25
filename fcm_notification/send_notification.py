import frappe
import requests
import json
from google.oauth2 import service_account
from google.auth.transport.requests import Request

logger = frappe.logger("fcm_notification", allow_site=True)

SKIP_DOCTYPES = {"FCM Notification", "FCM Notification Settings", "User Device"}


def send_fcm_message(doc, method):
    """
    Send a message to Firebase when the status is "NEW".
    Triggered via doc_events after_insert on FCM Notification.
    """
    if doc.status != "NEW":
        return

    if not doc.all_users and not doc.user:
        logger.debug(f"FCM Notification {doc.name}: no user or all_users flag set, skipping.")
        return

    if not doc.all_users:
        device_token = frappe.db.get_value("User Device", doc.user, "device_token")
        if not device_token:
            logger.debug(f"FCM Notification {doc.name}: User Device {doc.user} has no token, skipping.")
            return

    service_account_json = frappe.db.get_single_value("FCM Notification Settings", "server_key")
    if not service_account_json:
        frappe.throw("The service account JSON content is not configured in FCM Notification Settings.")

    try:
        service_account_info = json.loads(service_account_json)
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=["https://www.googleapis.com/auth/firebase.messaging"]
        )
    except Exception as e:
        frappe.throw(f"Error loading service account credentials: {e}")

    try:
        credentials.refresh(Request())
        access_token = credentials.token
    except Exception as e:
        frappe.throw(f"Error getting OAuth 2.0 access token: {e}")

    tokens_to_notify = []
    if doc.all_users:
        devices = frappe.get_all("User Device", fields=["device_token"])
        tokens_to_notify = [d.device_token for d in devices if d.device_token]
    else:
        token = frappe.db.get_value("User Device", doc.user, "device_token")
        if token:
            tokens_to_notify.append(token)

    if not tokens_to_notify:
        logger.warning(f"FCM Notification {doc.name}: No device tokens found to notify.")
        return

    project_id = credentials.project_id
    url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; UTF-8",
    }

    all_sent = True
    for token_to_notify in tokens_to_notify:
        message = {
            "message": {
                "notification": {
                    "title": doc.subject,
                    "body": doc.message
                },
                "token": token_to_notify,
            }
        }

        try:
            response = requests.post(url, headers=headers, data=json.dumps(message))

            if response.status_code == 200:
                logger.info(f"FCM message sent successfully for {doc.name} to token {token_to_notify[:20]}...")
            else:
                all_sent = False
                frappe.log_error(
                    title="FCM Notification Send Error",
                    message=f"Error sending FCM message for {doc.name}: {response.status_code} - {response.text}"
                )
        except Exception as e:
            all_sent = False
            frappe.log_error(
                title="FCM Notification Request Error",
                message=f"Exception sending FCM message for {doc.name}: {str(e)}"
            )

    if all_sent:
        frappe.db.set_value("FCM Notification", doc.name, "status", "SENT", update_modified=False)


def notification_handler(doc, method):
    """
    Handle the notification before validation and create FCM notification based on conditions.
    """
    if doc.channel != "FCM":
        return

    if not doc.enabled:
        return

    if not doc.document_type:
        frappe.throw("Document Type is required for FCM notifications")


def process_document_for_fcm(doc, method):
    """
    Called on monitored document events to check for matching FCM Notifications
    and dispatch them.
    """
    if doc.doctype in SKIP_DOCTYPES:
        return

    if frappe.flags.get("in_fcm_notification"):
        return

    notifications = frappe.get_all(
        "Notification",
        filters={
            "enabled": 1,
            "channel": "FCM",
            "document_type": doc.doctype
        },
        fields=["name", "subject", "message", "condition"],
    )

    if not notifications:
        return

    for notification in notifications:
        try:
            if notification.condition:
                context = {"doc": doc}
                if not frappe.safe_eval(notification.condition, eval_locals=context):
                    continue

            context = {"doc": doc}
            subject = frappe.render_template(
                notification.subject or f"Notification: {doc.doctype} {doc.name}",
                context
            )
            message_template = notification.message or ""
            message = frappe.render_template(message_template, context)

            notification_doc = frappe.get_doc("Notification", notification.name)
            recipients = resolve_notification_recipients(notification_doc, doc)

            if recipients:
                for user_email in recipients:
                    user_devices = frappe.get_all(
                        "User Device",
                        filters={"user": user_email},
                        fields=["name"]
                    )
                    for device in user_devices:
                        create_fcm_notification(subject, message, device.name, False, doc)
            else:
                create_fcm_notification(subject, message, None, True, doc)

        except Exception as e:
            frappe.log_error(
                title="FCM Notification Processing Error",
                message=f"Error processing notification {notification.name} for {doc.doctype} {doc.name}: {str(e)}"
            )


def resolve_notification_recipients(notification_doc, source_doc):
    """
    Resolve user emails from a Notification's recipients child table.
    Supports receiver types: by document field, by role, or custom email.
    """
    recipients = set()

    if not notification_doc.get("recipients"):
        return list(recipients)

    for row in notification_doc.recipients:
        try:
            if row.condition:
                context = {"doc": source_doc}
                if not frappe.safe_eval(row.condition, eval_locals=context):
                    continue

            receiver_by = getattr(row, "receiver_by", None) or getattr(row, "receiver_by_document_field", None) and "Document Field"

            if getattr(row, "receiver_by_document_field", None):
                field_value = source_doc.get(row.receiver_by_document_field)
                if field_value:
                    recipients.add(field_value)

            if getattr(row, "receiver_by_role", None):
                role_users = frappe.get_all(
                    "Has Role",
                    filters={"role": row.receiver_by_role, "parenttype": "User"},
                    fields=["parent"],
                )
                for u in role_users:
                    user = u.parent
                    if user and frappe.db.get_value("User", user, "enabled"):
                        recipients.add(user)

            if getattr(row, "cc", None):
                for email in row.cc.split(","):
                    email = email.strip()
                    if email:
                        recipients.add(email)

        except Exception as e:
            frappe.log_error(
                title="FCM Recipient Resolution Error",
                message=f"Error resolving recipient row: {str(e)}"
            )

    recipients.discard("Administrator")
    recipients.discard("Guest")

    return list(recipients)


def create_fcm_notification(subject, message, user=None, all_users=False, reference_doc=None):
    """
    Create FCM Notification document, triggering send_fcm_message via after_insert.
    """
    try:
        frappe.flags.in_fcm_notification = True

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
    finally:
        frappe.flags.in_fcm_notification = False
