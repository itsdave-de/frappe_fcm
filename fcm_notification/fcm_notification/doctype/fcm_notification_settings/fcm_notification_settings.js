// Copyright (c) 2022, Raheeb and contributors
// For license information, please see license.txt

frappe.ui.form.on('FCM Notification Settings', {
	refresh: function(frm) {
		frm.add_custom_button(__('Test Connection'), function() {
			test_fcm_connection(frm);
		}, __('FCM'));

		frm.add_custom_button(__('Send Test Notification'), function() {
			show_test_notification_dialog(frm);
		}, __('FCM'));
	}
});

function test_fcm_connection(frm) {
	if (!frm.doc.server_key) {
		frappe.msgprint(__('Please configure the Service Account Key (JSON) first.'));
		return;
	}

	frappe.call({
		method: 'fcm_notification.fcm_notification.doctype.fcm_notification_settings.fcm_notification_settings.test_fcm_connection',
		freeze: true,
		freeze_message: __('Testing FCM connection...'),
		callback: function(r) {
			if (!r.message) return;

			let result = r.message;
			let steps_html = result.steps.map(function(s) {
				let icon = s.status === 'ok'
					? '<span style="color: green; font-weight: bold;">&#10003;</span>'
					: '<span style="color: red; font-weight: bold;">&#10007;</span>';
				return `<tr>
					<td>${icon}</td>
					<td><strong>${s.step}</strong></td>
					<td>${s.detail}</td>
				</tr>`;
			}).join('');

			let status_msg = result.success
				? '<p style="color: green; font-weight: bold; font-size: 14px;">&#10003; Connection successful!</p>'
				: '<p style="color: red; font-weight: bold; font-size: 14px;">&#10007; Connection failed</p>';

			let project_info = result.project_id
				? `<p><strong>Firebase Project:</strong> ${result.project_id}</p>`
				: '';

			frappe.msgprint({
				title: __('FCM Connection Test'),
				indicator: result.success ? 'green' : 'red',
				message: `
					${status_msg}
					${project_info}
					<table class="table table-bordered table-sm" style="margin-top: 10px;">
						<thead><tr><th></th><th>Step</th><th>Details</th></tr></thead>
						<tbody>${steps_html}</tbody>
					</table>
				`
			});
		}
	});
}

function show_test_notification_dialog(frm) {
	if (!frm.doc.server_key) {
		frappe.msgprint(__('Please configure the Service Account Key (JSON) first.'));
		return;
	}

	let d = new frappe.ui.Dialog({
		title: __('Send Test Notification'),
		fields: [
			{
				fieldname: 'device',
				fieldtype: 'Link',
				label: __('User Device'),
				options: 'User Device',
				reqd: 1,
				description: __('Select a registered device to send the test notification to.')
			}
		],
		primary_action_label: __('Send Test'),
		primary_action: function(values) {
			d.hide();
			frappe.call({
				method: 'fcm_notification.fcm_notification.doctype.fcm_notification_settings.fcm_notification_settings.send_test_notification',
				args: { device_name: values.device },
				freeze: true,
				freeze_message: __('Sending test notification...'),
				callback: function(r) {
					if (!r.message) return;

					let result = r.message;

					if (result.success) {
						frappe.msgprint({
							title: __('Test Notification Sent'),
							indicator: 'green',
							message: `
								<p style="color: green; font-weight: bold;">&#10003; ${result.message}</p>
								<p><strong>Device:</strong> ${result.device}</p>
								<p><strong>User:</strong> ${result.user}</p>
								<p style="margin-top: 10px; color: #666;">
									Check the device to confirm the notification was received.
								</p>
							`
						});
					} else {
						let error_html = result.error
							? `<pre style="max-height: 200px; overflow-y: auto; font-size: 12px;">${frappe.utils.escape_html(result.error)}</pre>`
							: '';

						frappe.msgprint({
							title: __('Test Notification Failed'),
							indicator: 'red',
							message: `
								<p style="color: red; font-weight: bold;">&#10007; ${result.message}</p>
								<p><strong>HTTP Status:</strong> ${result.status_code}</p>
								<p><strong>Device:</strong> ${result.device}</p>
								${error_html}
							`
						});
					}
				}
			});
		}
	});

	d.show();
}
