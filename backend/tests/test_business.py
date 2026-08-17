import uuid

import pytest
from fastapi.testclient import TestClient

from main import app
from database import SessionLocal
from models import Role, BusinessCategory, Country, Business, BusinessMember, AuditLog, User

client = TestClient(app)


ROLE_SEED = [
    ("PLATFORM_ADMIN", "Platform Administrator"),
    ("BUSINESS_OWNER", "Business Owner"),
    ("BRANCH_MANAGER", "Branch Manager"),
    ("HR_USER", "Human Resource User"),
    ("RESOURCE_USER", "Resource User"),
    ("CUSTOMER", "Customer"),
]


@pytest.fixture(scope="module", autouse=True)
def seed_reference_data():
    """
    Migrations seed roles/categories/countries in real deployments; the test
    suite builds its schema via Base.metadata.create_all (see conftest.py)
    without running Alembic data migrations, so reference data is seeded
    here instead. Idempotent so it is safe alongside other test modules.
    """
    db = SessionLocal()
    try:
        for code, name in ROLE_SEED:
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

    yield


def _category_id():
    db = SessionLocal()
    try:
        return db.query(BusinessCategory).filter(BusinessCategory.name == "Salon").first().id
    finally:
        db.close()


def _country_id():
    db = SessionLocal()
    try:
        return db.query(Country).filter(Country.iso_code == "IN").first().id
    finally:
        db.close()


def _register_business(business_name=None, username=None, email=None):
    unique = uuid.uuid4().hex[:8]
    payload = {
        "username": username or f"owner_{unique}",
        "email": email or f"{unique}@example.com",
        "password": "Testpass123",
        "business_name": business_name or f"Business {unique}",
        "business_category_id": _category_id(),
        "country_id": _country_id(),
    }
    return client.post("/api/v1/businesses/register", json=payload)


def _promote_to_platform_admin(username):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        role = db.query(Role).filter(Role.code == "PLATFORM_ADMIN").first()
        from models import UserRole
        db.add(UserRole(user_id=user.id, role_id=role.id))
        db.commit()
    finally:
        db.close()


def _login(username, password="Testpass123"):
    response = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


# -----------------------------
# Registration
# -----------------------------

def test_register_business_creates_pending_business_with_owner_membership_and_audit_log():
    unique = uuid.uuid4().hex[:8]
    username = f"regowner_{unique}"

    response = _register_business(username=username)
    assert response.status_code == 200, response.text

    data = response.json()
    assert data["status"] == "Pending"
    assert data["approved_by"] is None
    assert data["approved_at"] is None

    db = SessionLocal()
    try:
        business = db.query(Business).filter(Business.id == data["id"]).first()
        assert business is not None
        assert business.status == "Pending"

        owner_role = db.query(Role).filter(Role.code == "BUSINESS_OWNER").first()
        membership = db.query(BusinessMember).filter(
            BusinessMember.business_id == business.id,
            BusinessMember.user_id == business.owner_user_id,
        ).first()
        assert membership is not None
        assert membership.role_id == owner_role.id
        assert membership.status == "Active"

        audit_entry = db.query(AuditLog).filter(
            AuditLog.entity_type == "Business",
            AuditLog.entity_id == business.id,
            AuditLog.action == "BUSINESS_REGISTERED",
        ).first()
        assert audit_entry is not None
        assert audit_entry.performed_by == business.owner_user_id
    finally:
        db.close()


def test_pending_business_is_excluded_from_active_listing():
    unique = uuid.uuid4().hex[:8]
    admin_username = f"listadmin_{unique}"

    response = _register_business()
    assert response.status_code == 200
    business_id = response.json()["id"]

    _register_business(username=admin_username, email=f"{admin_username}@example.com")
    _promote_to_platform_admin(admin_username)
    admin_token = _login(admin_username)

    response = client.get(
        "/api/v1/businesses/",
        params={"status": "Active"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    active_ids = [b["id"] for b in response.json()]
    assert business_id not in active_ids


def test_duplicate_registration_for_same_owner_is_rejected():
    unique = uuid.uuid4().hex[:8]
    username = f"dupowner_{unique}"
    email = f"{unique}@example.com"

    first = _register_business(username=username, email=email)
    assert first.status_code == 200

    second = _register_business(username=username, email=email, business_name="Second Business")
    assert second.status_code == 409


# -----------------------------
# Platform Admin approval
# -----------------------------

def test_non_admin_cannot_approve_or_reject_business():
    response = _register_business()
    assert response.status_code == 200
    business_id = response.json()["id"]

    unique = uuid.uuid4().hex[:8]
    other_username = f"nonadmin_{unique}"
    other_reg = _register_business(username=other_username, email=f"{unique}@example.com")
    assert other_reg.status_code == 200

    token = _login(other_username)

    approve_response = client.post(
        f"/api/v1/businesses/{business_id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert approve_response.status_code == 403

    reject_response = client.post(
        f"/api/v1/businesses/{business_id}/reject",
        json={"reason": "not authorized anyway"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert reject_response.status_code == 403


def test_platform_admin_can_approve_business_and_audit_is_recorded():
    unique = uuid.uuid4().hex[:8]
    admin_username = f"approver_{unique}"

    target = _register_business()
    assert target.status_code == 200
    business_id = target.json()["id"]

    _register_business(username=admin_username, email=f"{admin_username}@example.com")
    _promote_to_platform_admin(admin_username)
    admin_token = _login(admin_username)

    response = client.post(
        f"/api/v1/businesses/{business_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text

    data = response.json()
    assert data["status"] == "Active"
    assert data["approved_by"] is not None
    assert data["approved_at"] is not None

    db = SessionLocal()
    try:
        audit_entry = db.query(AuditLog).filter(
            AuditLog.entity_type == "Business",
            AuditLog.entity_id == business_id,
            AuditLog.action == "BUSINESS_APPROVED",
        ).first()
        assert audit_entry is not None
        assert audit_entry.performed_by is not None
    finally:
        db.close()


def test_platform_admin_can_reject_business_with_reason_and_audit_is_recorded():
    unique = uuid.uuid4().hex[:8]
    admin_username = f"rejector_{unique}"

    target = _register_business()
    assert target.status_code == 200
    business_id = target.json()["id"]

    _register_business(username=admin_username, email=f"{admin_username}@example.com")
    _promote_to_platform_admin(admin_username)
    admin_token = _login(admin_username)

    response = client.post(
        f"/api/v1/businesses/{business_id}/reject",
        json={"reason": "Incomplete documentation"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "Rejected"

    db = SessionLocal()
    try:
        audit_entry = db.query(AuditLog).filter(
            AuditLog.entity_type == "Business",
            AuditLog.entity_id == business_id,
            AuditLog.action == "BUSINESS_REJECTED",
        ).first()
        assert audit_entry is not None
        assert audit_entry.reason == "Incomplete documentation"
    finally:
        db.close()


def test_cannot_approve_a_business_that_is_not_pending():
    unique = uuid.uuid4().hex[:8]
    admin_username = f"repeatadmin_{unique}"

    target = _register_business()
    business_id = target.json()["id"]

    _register_business(username=admin_username, email=f"{admin_username}@example.com")
    _promote_to_platform_admin(admin_username)
    admin_token = _login(admin_username)

    first = client.post(
        f"/api/v1/businesses/{business_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert first.status_code == 200

    second = client.post(
        f"/api/v1/businesses/{business_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert second.status_code == 409
