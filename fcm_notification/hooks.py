from . import __version__ as app_version

app_name = "fcm_notification"
app_title = "Fcm Notification"
app_publisher = "Raheeb"
app_description = "Sends Frappe notifications to devices via Firebase Cloud Message"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "rahibhassan.10@gmail.com"
app_license = "MIT"

after_install = "fcm_notification.install.after_install"
after_migrate = "fcm_notification.install.after_install"

# DocType Class Override
# ----------------------
# Add FCM as a native channel to Frappe's Notification system.
# This is the clean approach: Frappe's evaluate_alert handles condition
# checking and recipient resolution, our override adds the FCM dispatch.

override_doctype_class = {
    "Notification": "fcm_notification.notification_override.Notification"
}

# Document Events
# ---------------
# Only the FCM Notification delivery trigger remains.
# The wildcard hook on "*" has been removed - FCM is now dispatched
# through Frappe's standard notification system via the channel override.

doc_events = {
    "FCM Notification": {
        "after_insert": "fcm_notification.send_notification.send_fcm_message"
    },
}

# User Data Protection
# --------------------

user_data_fields = [
    {
        "doctype": "User Device",
        "filter_by": "user",
        "redact_fields": ["device_token", "device_id"],
        "partial": 1,
    },
    {
        "doctype": "FCM Notification",
        "filter_by": "user",
        "partial": 1,
    },
]
