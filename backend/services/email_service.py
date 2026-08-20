import smtplib
from email.message import EmailMessage
from config import get_settings

settings = get_settings()


def send_password_reset_email(email: str, token: str):

    reset_link = f"{settings.FRONTEND_BASE_URL}/reset-password?token={token}"

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


def send_staff_invitation_email(email: str, token: str, role_code: str, business_name: str):

    accept_link = f"{settings.FRONTEND_BASE_URL}/accept-invitation?token={token}"

    role_label = {
        "BRANCH_MANAGER": "Branch Manager",
        "HR_USER": "Human Resource User",
    }.get(role_code, role_code)

    msg = EmailMessage()
    msg["Subject"] = f"You've been invited to join {business_name}"
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = email

    msg.set_content(
        f"""
Hello,

You have been invited to join {business_name} as a {role_label}.

Click the link below to accept the invitation:

{accept_link}

This link expires in 7 days.

If you were not expecting this invitation, please ignore this email.
"""
    )

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)