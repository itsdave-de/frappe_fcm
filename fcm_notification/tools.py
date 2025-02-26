import frappe
from frappe import _
from frappe.utils import now

@frappe.whitelist()
def register_device(device_info):
    """
    Register a new device for push notifications.

    Args:
        device_info (dict): Information about the device to register.
            Required keys:
            - deviceId: Unique identifier for the device
            - fcmToken: Firebase Cloud Messaging token
            - platform: Device platform (android/ios)
            Optional keys:
            - deviceModel: Model of the device
            - deviceName: Name of the device
            - osVersion: Operating system version
    
    Returns:
        dict: Response with status and message
    
    Raises:
        frappe.ValidationError: If required fields are missing or invalid
    """
    try:
        if not isinstance(device_info, dict):
            device_info = frappe.parse_json(device_info)

        # Validate required fields
        required_fields = ['deviceId', 'fcmToken', 'platform']
        for field in required_fields:
            if not device_info.get(field):
                frappe.throw(_(f"Missing required field: {field}"))

        # Validate platform
        if device_info.get('platform').lower() not in ['android', 'ios']:
            frappe.throw(_("Platform must be either 'android' or 'ios'"))

        # Map the incoming data to DocType fields
        device_data = {
            "user": frappe.session.user,
            "device_id": device_info.get('deviceId'),
            "device_token": device_info.get('fcmToken'),
            "device_name": device_info.get('deviceName'),
            "device_model": device_info.get('deviceModel'),
            "os_version": device_info.get('osVersion'),
            "platform": device_info.get('platform').lower()
        }

        # Check if device already exists
        existing_device = frappe.get_all(
            "User Device",
            filters={"device_id": device_data["device_id"]},
            limit=1
        )

        if existing_device:
            # Update existing device
            doc = frappe.get_doc("User Device", existing_device[0].name)
            doc.update(device_data)
            doc.save()
            frappe.db.commit()
            return {
                "status": "success",
                "message": "Device updated successfully",
                "device": doc.name
            }
        else:
            # Create new device
            doc = frappe.get_doc({
                "doctype": "User Device",
                **device_data
            })
            doc.insert()
            frappe.db.commit()
            return {
                "status": "success",
                "message": "Device registered successfully",
                "device": doc.name
            }

    except frappe.ValidationError as e:
        frappe.db.rollback()
        return {
            "status": "error",
            "message": str(e)
        }
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(
            title="Device Registration Error",
            message=f"Error while registering device: {str(e)}\nDevice Info: {device_info}"
        )
        return {
            "status": "error",
            "message": "An error occurred while registering the device. Please try again later."
        }