# Copyright (c) 2026, itsdave GmbH
# License: MIT. See LICENSE

"""
Override for Frappe's Notification doctype to add FCM as a native channel.

Frappe's send_notification_by_channel dispatches to Email, Slack, SMS
and System Notification but has no FCM handler. This override adds FCM
as a first-class channel, using the same Notification configuration UI
(recipients, condition, subject, message template).
"""

import json

import frappe
from frappe.email.doctype.notification.notification import Notification as _OriginalNotification

from fcm_notification.send_notification import create_fcm_notification


class Notification(_OriginalNotification):
	def send_notification_by_channel(self, doc, context):
		"""Extend with FCM channel support.

		Mirrors Frappe's own pattern: the entire dispatch is wrapped in
		try/except so that a notification failure never crashes the parent
		document transaction (e.g. Auto Repeat creating an HD Ticket).
		"""
		if self.channel == "FCM":
			try:
				self.send_fcm(doc, context)

				if self.send_system_notification:
					self.create_system_notification(doc, context)
			except Exception:
				self.log_error("Failed to send FCM Notification")
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
			return

		for user_email in users:
			if not _can_read_doc(user_email, doc):
				continue

			user_devices = frappe.get_all(
				"User Device",
				filters={"user": user_email},
				fields=["name"],
			)
			for device in user_devices:
				create_fcm_notification(subject, message, device.name, False, doc)


def _can_read_doc(user_email, doc):
	"""Check if a user can read a document without touching frappe.session.

	For HD Ticket: replicates helpdesk's has_permission logic using direct
	DB queries instead of frappe.set_user(), which destroys session state
	(sid, csrf_token, form_dict) when called in a web request context.

	For other doctypes: delegates to frappe.has_permission(user=...) which
	works correctly because their permission hooks use the user parameter.
	"""
	if doc.doctype == "HD Ticket":
		return _can_read_ticket(user_email, doc)

	try:
		return frappe.has_permission(
			doc.doctype, "read", doc=doc.name, user=user_email
		)
	except Exception:
		return False


def _can_read_ticket(user_email, doc):
	"""Check if user can read an HD Ticket via direct DB queries.

	Mirrors the logic in helpdesk.helpdesk.doctype.hd_ticket.hd_ticket.has_permission
	but replaces get_agents_team() (which hardcodes frappe.session.user) with
	a parameterized SQL query.
	"""
	# 1. Direct association: contact, raised_by, owner
	if user_email in (doc.contact, doc.raised_by, doc.owner):
		return True

	if user_email == "Administrator":
		return True

	# 2. Customer check
	if doc.get("customer"):
		from helpdesk.utils import get_customer
		if doc.customer in get_customer(user_email):
			return True

	# 3. Must be an agent to see other tickets
	if not _is_agent(user_email):
		return False

	# 4. Team restriction settings
	restrict = frappe.db.get_single_value(
		"HD Settings", "restrict_tickets_by_agent_group"
	)
	if not restrict:
		return True

	allow_no_team = frappe.db.get_single_value(
		"HD Settings", "do_not_restrict_tickets_without_an_agent_group"
	)
	if allow_no_team and not doc.get("agent_group"):
		return True

	# 5. Assigned to this ticket
	assign_raw = doc.get("_assign")
	if assign_raw:
		try:
			assignees = json.loads(assign_raw) if isinstance(assign_raw, str) else assign_raw
			if user_email in assignees:
				return True
		except (json.JSONDecodeError, TypeError):
			pass

	# 6. Team membership (replaces get_agents_team() which uses session.user)
	teams = frappe.db.sql(
		"""
		SELECT t.team_name, t.ignore_restrictions
		FROM `tabHD Team Member` tm
		JOIN `tabHD Team` t ON t.name = tm.parent
		WHERE tm.user = %s
		""",
		user_email,
		as_dict=True,
	)

	if any(t.get("ignore_restrictions") for t in teams):
		return True

	team_names = [t.team_name for t in teams]
	if doc.get("agent_group") and doc.agent_group in team_names:
		return True

	return False


def _is_agent(user_email):
	"""Check if user is an agent without using frappe.session."""
	roles = frappe.get_roles(user_email)
	return (
		"Agent" in roles
		or "Agent Manager" in roles
		or bool(frappe.db.exists("HD Agent", {"name": user_email}))
	)
