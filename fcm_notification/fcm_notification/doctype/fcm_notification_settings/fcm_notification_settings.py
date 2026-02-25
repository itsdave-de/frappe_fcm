# Copyright (c) 2022, Raheeb and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
import json


class FCMNotificationSettings(Document):
	pass


@frappe.whitelist()
def test_fcm_connection():
	"""
	Validate the service account JSON and test OAuth2 token generation.
	Returns project_id and token status on success.
	"""
	from google.oauth2 import service_account
	from google.auth.transport.requests import Request

	server_key = frappe.db.get_single_value("FCM Notification Settings", "server_key")
	if not server_key:
		frappe.throw(_("Service Account Key (JSON) is not configured."))

	steps = []

	try:
		service_account_info = json.loads(server_key)
		steps.append({
			"step": "JSON Parse",
			"status": "ok",
			"detail": f"Project: {service_account_info.get('project_id', 'N/A')}"
		})
	except Exception as e:
		frappe.throw(_("Invalid JSON in Service Account Key: {0}").format(str(e)))

	required_keys = ["type", "project_id", "private_key", "client_email", "token_uri"]
	missing = [k for k in required_keys if k not in service_account_info]
	if missing:
		frappe.throw(
			_("Service Account JSON is missing required fields: {0}. "
			  "Make sure you are using the Firebase Admin SDK private key, "
			  "not the google-services.json file.").format(", ".join(missing))
		)

	if service_account_info.get("type") != "service_account":
		frappe.throw(
			_("Invalid JSON type: '{0}'. Expected 'service_account'. "
			  "Make sure this is a Firebase Admin SDK private key.").format(
				service_account_info.get("type")
			)
		)

	steps.append({
		"step": "Structure Validation",
		"status": "ok",
		"detail": f"Client: {service_account_info.get('client_email', 'N/A')}"
	})

	try:
		credentials = service_account.Credentials.from_service_account_info(
			service_account_info,
			scopes=["https://www.googleapis.com/auth/firebase.messaging"]
		)
		credentials.refresh(Request())
		steps.append({
			"step": "OAuth2 Token",
			"status": "ok",
			"detail": f"Token obtained (expires: {credentials.expiry})"
		})
	except Exception as e:
		steps.append({
			"step": "OAuth2 Token",
			"status": "error",
			"detail": str(e)
		})
		return {"steps": steps, "success": False}

	return {
		"steps": steps,
		"success": True,
		"project_id": service_account_info.get("project_id"),
	}


@frappe.whitelist()
def send_test_notification(device_name):
	"""
	Send a test push notification to a specific User Device.
	Validates the full pipeline: credentials -> token -> HTTP request -> FCM response.
	"""
	from google.oauth2 import service_account
	from google.auth.transport.requests import Request
	import requests

	if not device_name:
		frappe.throw(_("Please select a device to send the test notification to."))

	device = frappe.get_doc("User Device", device_name)
	if not device.device_token:
		frappe.throw(_("Selected device does not have an FCM token."))

	server_key = frappe.db.get_single_value("FCM Notification Settings", "server_key")
	if not server_key:
		frappe.throw(_("Service Account Key (JSON) is not configured."))

	service_account_info = json.loads(server_key)
	credentials = service_account.Credentials.from_service_account_info(
		service_account_info,
		scopes=["https://www.googleapis.com/auth/firebase.messaging"]
	)
	credentials.refresh(Request())

	project_id = credentials.project_id
	url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"

	message = {
		"message": {
			"notification": {
				"title": "FCM Test - Frappe",
				"body": f"Test notification sent at {frappe.utils.now_datetime().strftime('%H:%M:%S %d/%m/%Y')}. If you see this, FCM is working!"
			},
			"token": device.device_token,
		}
	}

	response = requests.post(
		url,
		headers={
			"Authorization": f"Bearer {credentials.token}",
			"Content-Type": "application/json; UTF-8",
		},
		data=json.dumps(message),
		timeout=30,
	)

	if response.status_code == 200:
		response_data = response.json()
		return {
			"success": True,
			"message": _("Test notification sent successfully!"),
			"fcm_response": response_data,
			"device": device.device_name or device.name,
			"user": device.user,
		}
	else:
		error_detail = response.text
		try:
			error_json = response.json()
			error_detail = json.dumps(error_json, indent=2)
		except Exception:
			pass

		return {
			"success": False,
			"message": _("FCM returned an error"),
			"status_code": response.status_code,
			"error": error_detail,
			"device": device.device_name or device.name,
		}
