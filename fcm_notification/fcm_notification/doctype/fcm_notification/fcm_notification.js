// Copyright (c) 2025, Raheeb and contributors
// For license information, please see license.txt

frappe.ui.form.on('FCM Notification', {
    all_users: function (frm) {
        if (frm.doc.all_users) {
            // clean the user field and make it read only
            frm.set_value('user', null);
            frm.set_df_property('user', 'read_only', 1);
        } else {
            // Set the user field to be editable
            frm.set_df_property('user', 'read_only', 0);
        }
    }
});
