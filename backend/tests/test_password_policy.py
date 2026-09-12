import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from main import app
from auth import validate_password

client = TestClient(app)


# -----------------------------
# validate_password() — PRD §33.3 (M9 Phase 3: special-character rule added)
# -----------------------------

def test_validate_password_accepts_a_password_meeting_all_five_rules():
    validate_password("Testpass123!")  # must not raise


@pytest.mark.parametrize(
    "password",
    [
        "short1!A",  # 8 chars, meets every rule — sanity baseline, should pass
    ],
)
def test_validate_password_accepts_minimum_length_with_all_classes(password):
    validate_password(password)


def test_validate_password_rejects_missing_special_character():
    with pytest.raises(HTTPException) as excinfo:
        validate_password("Testpass123")
    assert excinfo.value.status_code == 400
    assert "special character" in excinfo.value.detail.lower()


def test_validate_password_rejects_too_short():
    with pytest.raises(HTTPException) as excinfo:
        validate_password("Ab1!")
    assert excinfo.value.status_code == 400


def test_validate_password_rejects_missing_uppercase():
    with pytest.raises(HTTPException):
        validate_password("testpass123!")


def test_validate_password_rejects_missing_lowercase():
    with pytest.raises(HTTPException):
        validate_password("TESTPASS123!")


def test_validate_password_rejects_missing_number():
    with pytest.raises(HTTPException):
        validate_password("Testpassword!")


# -----------------------------
# Enforced at the /auth/register endpoint (one of the four shared call sites)
# -----------------------------

def test_register_rejects_password_without_special_character():
    unique = uuid.uuid4().hex[:8]
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": f"nospecial_{unique}",
            "email": f"{unique}@example.com",
            "password": "Testpass123",
        },
    )
    assert response.status_code == 400
    assert "special character" in response.json()["error"]["message"].lower()


def test_register_accepts_password_with_special_character():
    unique = uuid.uuid4().hex[:8]
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": f"withspecial_{unique}",
            "email": f"{unique}@example.com",
            "password": "Testpass123!",
        },
    )
    assert response.status_code == 200, response.text
