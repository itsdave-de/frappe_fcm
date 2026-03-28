# Copyright (c) 2026, itsdave GmbH
# License: MIT. See LICENSE

"""
Override for Frappe's Notification doctype to add FCM as a native channel.

Frappe's send_notification_by_channel dispatches to Email, Slack, SMS
and System Notification but has no FCM handler. This override adds FCM
as a first-class channel, using the same Notification configuration UI
(recipients, condition, subject, message template).

This replaces the previous approach of using a wildcard doc_events hook
(process_document_for_fcm) which ran on every document event of every
doctype and bypassed Frappe's notification system entirely.
"""

import frappe
from frappe.email.doctype.notification.notification import Notification as _OriginalNotification

from fcm_notification.send_notification import create_fcm_notification


class Notification(_OriginalNotification):
	def send_notification_by_channel(self, doc, context):
		"""Extend with FCM channel support."""
		if self.channel == "FCM":
			self.send_fcm(doc, context)

			if self.send_system_notification:
				self.create_system_notification(doc, context)
			return

		# All other channels: delegate to original implementation
		super().send_notification_by_channel(doc, context)

	def send_fcm(self, doc, context):
		"""Send FCM push notification to resolved recipients."""
		subject = self.subject or ""
		if "{" in subject:
			subject = frappe.render_template(self.subject, context)

		message = ""
		if self.message:
			message = frappe.render_template(self.message, context)

		recipients, cc, bcc = self.get_list_of_recipients(doc, context)
		users = set(recipients + cc + bcc)
		users.discard("Administrator")
		users.discard("Guest")

		if not users:
			# No recipients configured: do nothing (no broadcast)
			return

		for user_email in users:
			# Only notify users who have permission to read the document
			if not frappe.has_permission(
				doc.doctype, "read", doc=doc.name, user=user_email
			):
				continue

			user_devices = frappe.get_all(
				"User Device",
				filters={"user": user_email},
				fields=["name"],
			)
			for device in user_devices:
				create_fcm_notification(subject, message, device.name, False, doc)
