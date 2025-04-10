import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from itsdangerous import URLSafeTimedSerializer

class EmailService:
    def __init__(self, app):
        self.serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        self.sendgrid_api_key = app.config['SENDGRID_API_KEY']
        self.sender_email = app.config['MAIL_DEFAULT_SENDER']
        self.salt = 'password-reset-salt'

    def generate_token(self, email):
        return self.serializer.dumps(email, salt=self.salt)

    def verify_token(self, token, max_age=3600):
        try:
            email = self.serializer.loads(token, salt=self.salt, max_age=max_age)
            return email
        except Exception as e:
            return None

    def send_email(self, to_email, subject, html_content):
        message = Mail(
            from_email=self.sender_email,
            to_emails=to_email,
            subject=subject,
            html_content=html_content
        )
        try:
            sg = SendGridAPIClient(self.sendgrid_api_key)
            response = sg.send(message)
            return response
        except Exception as e:
            print(f"An error occurred while sending the email: {e}")
            return None