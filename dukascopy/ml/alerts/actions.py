import requests
import smtplib
from email.message import EmailMessage
from typing import Dict, Any

class BaseAction:
    def execute(self, params: Dict[str, Any], payload: Dict[str, Any]):
        raise NotImplementedError("Subclasses must implement execute()")

class WebhookAction(BaseAction):
    def execute(self, params: Dict[str, Any], payload: Dict[str, Any]):
        uri = params.get('uri')
        method = params.get('method', 'POST').upper()
        
        try:
            if method == 'POST':
                response = requests.post(uri, json=payload, timeout=10)
            elif method == 'GET':
                response = requests.get(uri, params=payload, timeout=10)
            print(f"[Webhook] Sent to {uri} - Status: {response.status_code}")
        except Exception as e:
            print(f"[Webhook] Failed to send to {uri}: {e}")

class EmailActionGmail(BaseAction):
    def execute(self, params: Dict[str, Any], payload: Dict[str, Any]):
        print("Executing action gmail")
        
        address = params.get('address')
        subject = params.get('subject', 'Alert Triggered')
        
        smtp_server = params.get('smtp_server', 'smtp.gmail.com')
        smtp_port = int(params.get('smtp_port', 587))
        username = params.get('username')
        password = params.get('password')
        
        from_address = params.get('from_address', username)

        if not username or not password:
            print(f"[Email Error] Missing credentials for {address}. Cannot send.")
            return
        
        msg = EmailMessage()
        msg.set_content(f"Alert triggered with data:\n{payload}")
        msg['Subject'] = subject
        msg['From'] = from_address
        msg['To'] = address

        try:
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.ehlo()              # Identify ourselves to the server
                server.starttls()          # Upgrade the connection to secure TLS
                server.ehlo()              # Re-identify over the secure connection
                server.login(username, password) # Authenticate with Gmail App Password
                server.send_message(msg)   # Send
                
            print(f"[Email] Successfully sent via Gmail to {address}")
        except Exception as e:
            print(f"[Email] Failed to send via Gmail to {address}: {e}")

class EmailAction(BaseAction):
    def execute(self, params: Dict[str, Any], payload: Dict[str, Any]):
        address = params.get('address')
        subject = params.get('subject', 'Alert Triggered')
        
        msg = EmailMessage()
        msg.set_content(f"Alert triggered with data:\n{payload}")
        msg['Subject'] = subject
        msg['From'] = "alerts@yourdomain.com"
        msg['To'] = address

        try:
            with smtplib.SMTP('localhost', 1025) as server:
                server.send_message(msg)
            print(f"[Email] Sent to {address}")
        except Exception as e:
            print(f"[Email] Failed to send to {address}: {e}")

class ActionFactory:
    _actions = {
        'webhook': WebhookAction(),
        'gmail': EmailActionGmail(),
        'mail': EmailAction()
    }

    @classmethod
    def dispatch(cls, action_type: str, params: Dict[str, Any], payload: Dict[str, Any]):
        action = cls._actions.get(action_type.lower())
        if action:
            action.execute(params, payload)
        else:
            print(f"[Action Error] Unknown action type: {action_type}")