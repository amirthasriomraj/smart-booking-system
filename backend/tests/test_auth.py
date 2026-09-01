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
    # /api/v1/bookings was the legacy example protected route; the Milestone 7
    # Booking Engine replaced it with tenant/branch-scoped booking paths (no bare
    # collection endpoint), so /auth/me stands in as "any protected route" here.
    response = client.get("/api/v1/auth/me")

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
        "/api/v1/auth/me",
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


# -----------------------------
# /auth/me context (Milestone 2 — drives frontend role-gating)
# -----------------------------

def _seed_me_reference_data():
    from database import SessionLocal
    from models import Role, BusinessCategory, Country

    db = SessionLocal()
    try:
        for code, name in [("PLATFORM_ADMIN", "Platform Administrator"), ("BUSINESS_OWNER", "Business Owner")]:
            if not db.query(Role).filter(Role.code == code).first():
                db.add(Role(code=code, name=name))
        db.commit()

        if not db.query(BusinessCategory).filter(BusinessCategory.name == "Salon").first():
            db.add(BusinessCategory(name="Salon", is_active=True))
        db.commit()

        if not db.query(Country).filter(Country.iso_code == "IN").first():
            db.add(Country(iso_code="IN", name="India", currency_code="INR", timezone="Asia/Kolkata"))
        db.commit()
    finally:
        db.close()


def test_me_returns_plain_user_context():
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "plainmeuser",
            "email": "plainme@example.com",
            "password": "Testpass123"
        }
    )
    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "plainmeuser", "password": "Testpass123"}
    )
    access_token = login_response.json()["access_token"]

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "plainmeuser"
    assert data["is_platform_admin"] is False
    assert data["business"] is None


def test_me_returns_platform_admin_context():
    _seed_me_reference_data()

    client.post(
        "/api/v1/auth/register",
        json={
            "username": "meadmin",
            "email": "meadmin@example.com",
            "password": "Testpass123"
        }
    )

    from database import SessionLocal
    from models import User, Role, UserRole

    db = SessionLocal()
    user = db.query(User).filter(User.username == "meadmin").first()
    role = db.query(Role).filter(Role.code == "PLATFORM_ADMIN").first()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.commit()
    db.close()

    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "meadmin", "password": "Testpass123"}
    )
    access_token = login_response.json()["access_token"]

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == 200
    assert response.json()["is_platform_admin"] is True


def test_me_returns_business_owner_context():
    _seed_me_reference_data()

    from database import SessionLocal
    from models import BusinessCategory, Country

    db = SessionLocal()
    category_id = db.query(BusinessCategory).filter(BusinessCategory.name == "Salon").first().id
    country_id = db.query(Country).filter(Country.iso_code == "IN").first().id
    db.close()

    client.post(
        "/api/v1/businesses/register",
        json={
            "username": "meowner",
            "email": "meowner@example.com",
            "password": "Testpass123",
            "business_name": "Me Owner Business",
            "business_category_id": category_id,
            "country_id": country_id,
        }
    )

    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "meowner", "password": "Testpass123"}
    )
    access_token = login_response.json()["access_token"]

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["is_platform_admin"] is False
    assert data["business"] is not None
    assert data["business"]["role_code"] == "BUSINESS_OWNER"
    assert data["business"]["status"] == "Pending"