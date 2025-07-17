import frappe
from frappe import _
from frappe.utils import now
import traceback

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
        # Log the incoming request
        frappe.log_error(
            title="Device Registration - Incoming Request",
            message=f"Raw device_info: {device_info}\nType: {type(device_info)}\nUser: {frappe.session.user}"
        )
        
        if not isinstance(device_info, dict):
            try:
                device_info = frappe.parse_json(device_info)
                frappe.log_error(
                    title="Device Registration - JSON Parsed",
                    message=f"Parsed device_info: {device_info}"
                )
            except Exception as parse_error:
                frappe.log_error(
                    title="Device Registration - JSON Parse Error",
                    message=f"Failed to parse device_info: {device_info}\nError: {str(parse_error)}\nTraceback: {traceback.format_exc()}"
                )
                raise

        # Validate required fields
        required_fields = ['deviceId', 'fcmToken', 'platform']
        for field in required_fields:
            if not device_info.get(field):
                error_msg = f"Missing required field: {field}"
                frappe.log_error(
                    title="Device Registration - Missing Field",
                    message=f"Validation failed: {error_msg}\nDevice Info: {device_info}"
                )
                frappe.throw(_(error_msg))

        # Validate platform
        platform = device_info.get('platform')
        if platform and platform.lower() not in ['android', 'ios']:
            error_msg = "Platform must be either 'android' or 'ios'"
            frappe.log_error(
                title="Device Registration - Invalid Platform",
                message=f"Validation failed: {error_msg}\nProvided platform: {platform}\nDevice Info: {device_info}"
            )
            frappe.throw(_(error_msg))

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
        
        frappe.log_error(
            title="Device Registration - Mapped Data",
            message=f"Mapped device_data: {device_data}"
        )

        # Check if device already exists
        try:
            existing_device = frappe.get_all(
                "User Device",
                filters={"device_id": device_data["device_id"]},
                limit=1
            )
            
            frappe.log_error(
                title="Device Registration - Existing Device Check",
                message=f"Existing device query result: {existing_device}\nFilter: device_id = {device_data['device_id']}"
            )
        except Exception as db_error:
            frappe.log_error(
                title="Device Registration - Database Query Error",
                message=f"Error querying existing device: {str(db_error)}\nTraceback: {traceback.format_exc()}\nDevice ID: {device_data['device_id']}"
            )
            raise

        if existing_device:
            # Update existing device
            try:
                doc = frappe.get_doc("User Device", existing_device[0].name)
                frappe.log_error(
                    title="Device Registration - Updating Existing Device",
                    message=f"Found existing device: {existing_device[0].name}\nOld data: {doc.as_dict()}\nNew data: {device_data}"
                )
                doc.update(device_data)
                doc.save()
                frappe.db.commit()
                
                frappe.log_error(
                    title="Device Registration - Update Success",
                    message=f"Device updated successfully: {doc.name}"
                )
                
                return {
                    "status": "success",
                    "message": "Device updated successfully",
                    "device": doc.name
                }
            except Exception as update_error:
                frappe.log_error(
                    title="Device Registration - Update Error",
                    message=f"Error updating device: {str(update_error)}\nTraceback: {traceback.format_exc()}\nDevice: {existing_device[0].name}\nData: {device_data}"
                )
                raise
        else:
            # Create new device
            try:
                doc = frappe.get_doc({
                    "doctype": "User Device",
                    **device_data
                })
                
                frappe.log_error(
                    title="Device Registration - Creating New Device",
                    message=f"Creating new device with data: {device_data}"
                )
                
                doc.insert()
                frappe.db.commit()
                
                frappe.log_error(
                    title="Device Registration - Create Success",
                    message=f"Device created successfully: {doc.name}"
                )
                
                return {
                    "status": "success",
                    "message": "Device registered successfully",
                    "device": doc.name
                }
            except Exception as create_error:
                frappe.log_error(
                    title="Device Registration - Create Error",
                    message=f"Error creating device: {str(create_error)}\nTraceback: {traceback.format_exc()}\nData: {device_data}"
                )
                raise

    except frappe.ValidationError as e:
        frappe.db.rollback()
        frappe.log_error(
            title="Device Registration - Validation Error",
            message=f"Validation error: {str(e)}\nTraceback: {traceback.format_exc()}\nDevice Info: {device_info}"
        )
        return {
            "status": "error",
            "message": str(e)
        }
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(
            title="Device Registration - General Error",
            message=f"Unexpected error: {str(e)}\nTraceback: {traceback.format_exc()}\nDevice Info: {device_info}\nUser: {frappe.session.user}"
        )
        return {
            "status": "error",
            "message": "An error occurred while registering the device. Please try again later."
        }