# FCM Notification for Frappe

Send notifications created in Frappe as push notifications via Firebase Cloud Messaging (FCM).

Uses the FCM v1 HTTP API with OAuth 2.0 service account credentials.

## Installation

```bash
bench get-app https://github.com/user/fcm_notification
bench --site your-site install-app fcm_notification
```

## Setup

1. Go to **FCM Notification Settings** and paste your Firebase service account JSON key.
   - Obtain it from: Firebase Console > Project Settings > Service Accounts > Generate new private key.
   - This is **not** the `google-services.json` (which is for client-side Android apps).

2. Use the **Test Connection** button to verify credentials and OAuth2 token generation.

3. Use the **Send Test Notification** button to send a test push to a registered device.

## How it Works

- The app adds **FCM** as a channel option in the Frappe **Notification** DocType.
- When a document event matches a Notification rule with channel "FCM", a push notification is sent to the relevant user devices via a background job.
- Devices are registered via the `fcm_notification.tools.register_device` API endpoint.

## DocTypes

| DocType | Description |
|---------|-------------|
| **FCM Notification** | Log of sent push notifications |
| **FCM Notification Settings** | Firebase service account configuration (Single) |
| **User Device** | Registered devices with FCM tokens |

## API Endpoints

- `fcm_notification.tools.register_device` — Register or update a device for push notifications (requires authentication).

## License

MIT
