"""Environment configuration shared by local and cloud deployments."""

import os
import secrets


def app_settings():
    """Read configuration once, without storing secrets in source control."""
    production = bool(os.environ.get("DYNO"))
    secret = os.environ.get("SECRET_KEY")
    if production and not secret:
        raise ValueError("Set SECRET_KEY in Heroku Config Vars before starting Assety.")
    return {
        "SECRET_KEY": secret or secrets.token_hex(32),
        "DEBUG": not production and os.environ.get("FLASK_DEBUG") == "1",
        "MONGO_URI": os.environ.get("MONGO_URI"),
        "MONGO_DBNAME": os.environ.get("MONGO_DBNAME"),
        "MAX_CONTENT_LENGTH": 16 * 1024 * 1024,
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_SECURE": production,
        "SENDGRID_API_KEY": os.environ.get("SENDGRID_API_KEY"),
        "MAIL_DEFAULT_SENDER": os.environ.get("MAIL_DEFAULT_SENDER"),
    }
