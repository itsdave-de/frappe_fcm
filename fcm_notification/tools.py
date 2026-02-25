import frappe
from frappe import _

logger = frappe.logger("fcm_notification", allow_site=True)


@frappe.whitelist()
def register_device(device_info):
    """
    Register or update a device for push notifications.

    Args:
        device_info (dict): Device registration data with keys:
            - deviceId (required)
            - fcmToken (required)
            - platform (required): 'android' or 'ios'
            - deviceModel, deviceName, osVersion (optional)

    Returns:
        dict: Response with status, message and device name
    """
    try:
        if not isinstance(device_info, dict):
            device_info = frappe.parse_json(device_info)

        required_fields = ['deviceId', 'fcmToken', 'platform']
        for field in required_fields:
            if not device_info.get(field):
                frappe.throw(_(f"Missing required field: {field}"))

        platform = device_info.get('platform', '').lower()
        if platform not in ('android', 'ios'):
            frappe.throw(_("Platform must be either 'android' or 'ios'"))

        device_data = {
            "user": frappe.session.user,
            "device_id": device_info.get('deviceId'),
            "device_token": device_info.get('fcmToken'),
            "device_name": device_info.get('deviceName'),
            "device_model": device_info.get('deviceModel'),
            "os_version": device_info.get('osVersion'),
            "platform": platform,
        }

        existing_device = frappe.get_all(
            "User Device",
            filters={"device_id": device_data["device_id"]},
            fields=["name"],
            limit=1,
        )

        if existing_device:
            doc = frappe.get_doc("User Device", existing_device[0].name)
            doc.update(device_data)
            doc.save()
            return {
                "status": "success",
                "message": "Device updated successfully",
                "device": doc.name,
            }
        else:
            doc = frappe.get_doc({"doctype": "User Device", **device_data})
            doc.insert()
            return {
                "status": "success",
                "message": "Device registered successfully",
                "device": doc.name,
            }

    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.log_error(
            title="Device Registration Error",
            message=f"Error registering device for user {frappe.session.user}: {str(e)}",
        )
        frappe.throw(_("An error occurred while registering the device. Please try again later."))
