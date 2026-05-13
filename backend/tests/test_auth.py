from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_register_user():
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "Testpass123"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"


def test_login_user():
    # First register user
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "loginuser",
            "email": "login@example.com",
            "password": "Testpass123"
        }
    )

    # Now login
    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "loginuser",
            "password": "Testpass123"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_access_protected_route_without_token():
    response = client.get("/api/v1/bookings")

    assert response.status_code == 401


def test_access_protected_route_with_token():
    # Register user
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "protecteduser",
            "email": "protected@example.com",
            "password": "Testpass123"
        }
    )

    # Login user
    login_response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "protecteduser",
            "password": "Testpass123"
        }
    )

    access_token = login_response.json()["access_token"]

    # Access protected route
    response = client.get(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == 200


def test_user_cannot_access_admin_route():
    # Register normal user
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "normaluser",
            "email": "normal@example.com",
            "password": "Testpass123"
        }
    )

    # Login
    login_response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "normaluser",
            "password": "Testpass123"
        }
    )

    access_token = login_response.json()["access_token"]

    # Try admin-only endpoint
    response = client.get(
        "/api/v1/users/",
        headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == 403


def test_admin_can_access_admin_route():
    # Register user
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "adminuser",
            "email": "admin@example.com",
            "password": "Testpass123"
        }
    )

    # Promote user to admin
    from database import SessionLocal
    from models import User

    db = SessionLocal()

    user = db.query(User).filter(User.username == "adminuser").first()
    user.role = "admin"

    db.commit()
    db.close()

    # Login
    login_response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "adminuser",
            "password": "Testpass123"
        }
    )

    access_token = login_response.json()["access_token"]

    # Access admin endpoint
    response = client.get(
        "/api/v1/users/",
        headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == 200