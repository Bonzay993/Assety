import hashlib

from itsdangerous import URLSafeTimedSerializer
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


class EmailService:
    def __init__(self, app):
        self.logger = app.logger
        self.serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])
        self.sendgrid_api_key = app.config["SENDGRID_API_KEY"]
        self.sender_email = app.config["MAIL_DEFAULT_SENDER"]
        self.salt = "password-reset-salt"

    def generate_token(self, email, password_hash=None):
        payload = {"email": email}
        if password_hash is not None:
            payload["password_version"] = hashlib.sha256(
                password_hash.encode()
            ).hexdigest()
        return self.serializer.dumps(payload, salt=self.salt)

    def verify_token(self, token, max_age=3600, password_hash=None):
        try:
            payload = self.serializer.loads(token, salt=self.salt, max_age=max_age)
            if not isinstance(payload, dict) or not isinstance(
                payload.get("email"), str
            ):
                return None
            if (
                password_hash is not None
                and payload.get("password_version")
                != hashlib.sha256(password_hash.encode()).hexdigest()
            ):
                return None
            return payload["email"]
        except Exception:
            return None

    def send_email(self, to_email, subject, html_content):
        if not self.sendgrid_api_key or not self.sender_email:
            self.logger.warning(
                "Email delivery requires SENDGRID_API_KEY and MAIL_DEFAULT_SENDER"
            )
            return None
        message = Mail(
            from_email=self.sender_email,
            to_emails=to_email,
            subject=subject,
            html_content=html_content,
        )
        try:
            sg = SendGridAPIClient(self.sendgrid_api_key)
            response = sg.send(message)
            return response if 200 <= response.status_code < 300 else None
        except Exception as e:
            self.logger.warning("Email delivery failed (%s)", type(e).__name__)
            return None
