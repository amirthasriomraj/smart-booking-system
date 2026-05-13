from fastapi.testclient import TestClient
from main import app
import uuid


def create_user_and_login(password="Testpass123"):
    unique = uuid.uuid4().hex[:8]

    username = f"user_{unique}"
    email = f"{unique}@example.com"

    # NEW client each time with unique fake IP
    client = TestClient(
        app,
        headers={"X-Forwarded-For": f"192.168.1.{uuid.uuid4().int % 250}"}
    )

    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password
        }
    )

    assert register_response.status_code == 200, register_response.text

    login_response = client.post(
        "/api/v1/auth/login",
        data={
            "username": username,
            "password": password
        }
    )

    assert login_response.status_code == 200, login_response.text

    token = login_response.json()["access_token"]

    return client, {"Authorization": f"Bearer {token}"}


def test_user_cannot_update_other_users_booking():
    # User 1
    client1, user1_headers = create_user_and_login()

    booking_response = client1.post(
        "/api/v1/bookings/",
        json={
            "date": "2026-06-01",
            "time": "10:00:00"
        },
        headers=user1_headers
    )

    assert booking_response.status_code == 200, booking_response.text

    booking_id = booking_response.json()["id"]

    # User 2
    client2, user2_headers = create_user_and_login()

    response = client2.patch(
        f"/api/v1/bookings/{booking_id}",
        json={
            "date": "2026-06-02"
        },
        headers=user2_headers
    )

    assert response.status_code == 403