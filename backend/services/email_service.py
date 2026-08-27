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


def send_service_override_submitted_email(email: str, business_name: str, branch_name: str, service_name: str):
    """Notifies the Business Owner that a Branch Manager override needs review (ID-027, BR-058)."""

    msg = EmailMessage()
    msg["Subject"] = f"Service override pending approval — {business_name}"
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = email

    msg.set_content(
        f"""
Hello,

A Branch Manager at {branch_name} has submitted a change to "{service_name}" that requires your approval.

Please review it from your Service Management dashboard.
"""
    )

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)


def send_service_override_decision_email(
    email: str, business_name: str, branch_name: str, service_name: str, decision: str, comments: str = None
):
    """Notifies the submitting Branch Manager of the Business Owner's decision (ID-027, BR-058)."""

    msg = EmailMessage()
    msg["Subject"] = f"Service override {decision.lower()} — {business_name}"
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = email

    comments_line = f"\nComments: {comments}\n" if comments else ""

    msg.set_content(
        f"""
Hello,

Your proposed change to "{service_name}" at {branch_name} has been {decision.lower()}.
{comments_line}
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
        "RESOURCE_USER": "Resource User",
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