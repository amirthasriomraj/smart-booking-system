from fastapi.testclient import TestClient
from main import app
from database import SessionLocal
from models import AuditLog, User
import uuid

client = TestClient(app)


def create_test_user(password="Oldpass123!"):
    unique = uuid.uuid4().hex[:8]

    username = f"user_{unique}"
    email = f"{unique}@example.com"

    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password
        }
    )

    assert register_response.status_code == 200, register_response.text

    return username, email


def test_password_reset_flow(monkeypatch):
    captured = {}

    def fake_send_password_reset_email(email, token):
        captured["token"] = token
        return True

    monkeypatch.setattr(
        "routers.auth.send_password_reset_email",
        fake_send_password_reset_email
    )

    username, email = create_test_user()

    # Forgot password
    forgot_response = client.post(
        "/api/v1/auth/forgot-password",
        json={
            "email": email
        }
    )

    assert forgot_response.status_code == 200, forgot_response.text

    # Ensure token was captured
    assert "token" in captured

    raw_reset_token = captured["token"]

    # Reset password
    reset_response = client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": raw_reset_token,
            "new_password": "Newpass123!"
        }
    )

    assert reset_response.status_code == 200, reset_response.text

    # Old password should fail
    old_login = client.post(
        "/api/v1/auth/login",
        data={
            "username": username,
            "password": "Oldpass123!"
        }
    )

    assert old_login.status_code in [400, 401]

    # New password should work
    new_login = client.post(
        "/api/v1/auth/login",
        data={
            "username": username,
            "password": "Newpass123!"
        }
    )

    assert new_login.status_code == 200
    assert "access_token" in new_login.json()

    # M9 Phase 2: password reset writes an audit entry (PRD §30)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        audit_entry = db.query(AuditLog).filter(
            AuditLog.entity_type == "User",
            AuditLog.entity_id == user.id,
            AuditLog.action == "PASSWORD_RESET",
        ).first()
        assert audit_entry is not None
        assert audit_entry.performed_by == user.id
    finally:
        db.close()