import smtplib
from email.message import EmailMessage
from config import get_settings

settings = get_settings()


def send_password_reset_email(email: str, token: str):

    reset_link = f"http://localhost:5173/reset-password?token={token}"

    msg = EmailMessage()
    msg["Subject"] = "Password Reset Request"
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = email

    msg.set_content(
        f"""
Hello,

You requested a password reset.

Click the link below to reset your password:

{reset_link}

This link expires in 15 minutes.

If you did not request this, please ignore this email.
"""
    )

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)