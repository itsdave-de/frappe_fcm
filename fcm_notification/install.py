import frappe


def after_install():
    add_fcm_channel_to_notification()


def add_fcm_channel_to_notification():
    """Add 'FCM' as a channel option in the Notification doctype."""
    try:
        meta = frappe.get_meta("Notification")
        channel_field = meta.get_field("channel")
        if not channel_field:
            frappe.log_error(
                title="FCM Install",
                message="Could not find 'channel' field in Notification doctype."
            )
            return

        current_options = channel_field.options or ""
        options_list = [opt.strip() for opt in current_options.split("\n") if opt.strip()]

        if "FCM" in options_list:
            return

        options_list.append("FCM")
        new_options = "\n".join(options_list)

        property_setter_name = frappe.db.get_value(
            "Property Setter",
            {
                "doc_type": "Notification",
                "field_name": "channel",
                "property": "options",
            },
            "name",
        )

        if property_setter_name:
            frappe.db.set_value("Property Setter", property_setter_name, "value", new_options)
        else:
            frappe.make_property_setter({
                "doctype": "Notification",
                "fieldname": "channel",
                "property": "options",
                "value": new_options,
                "property_type": "Text",
            })

        frappe.clear_cache(doctype="Notification")
    except Exception as e:
        frappe.log_error(
            title="FCM Install - Channel Setup Error",
            message=f"Failed to add FCM channel to Notification doctype: {str(e)}"
        )
