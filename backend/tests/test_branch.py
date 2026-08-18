import uuid

import pytest
from fastapi.testclient import TestClient

from main import app
from database import SessionLocal
from models import Role, BusinessCategory, Country, Business, Branch, AuditLog, User, BranchWorkingHours

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
    response = client.post("/api/v1/businesses/register", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


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


def _register_and_approve_business():
    """Returns (business_id, owner_username, owner_token) for an Active business."""
    unique = uuid.uuid4().hex[:8]
    owner_username = f"activeowner_{unique}"
    business = _register_business(username=owner_username, email=f"{unique}@example.com")

    admin_username = f"branchadmin_{unique}"
    _register_business(username=admin_username, email=f"{admin_username}@example.com")
    _promote_to_platform_admin(admin_username)
    admin_token = _login(admin_username)

    approve = client.post(
        f"/api/v1/businesses/{business['id']}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert approve.status_code == 200, approve.text

    owner_token = _login(owner_username)
    return business["id"], owner_username, owner_token


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _create_branch(business_id, owner_token, branch_name=None):
    unique = uuid.uuid4().hex[:8]
    payload = {
        "branch_name": branch_name or f"Branch {unique}",
        "address": "1 Main St",
        "city": "Metropolis",
        "state": "State",
        "postal_code": "00000",
        "country_id": _country_id(),
        "phone": "1234567890",
        "email": f"{unique}@branch.example.com",
    }
    response = client.post(
        f"/api/v1/businesses/{business_id}/branches",
        json=payload,
        headers=_auth(owner_token),
    )
    assert response.status_code == 200, response.text
    return response.json()


# -----------------------------
# Creation
# -----------------------------

def test_business_owner_can_create_branch_for_active_business():
    business_id, _, owner_token = _register_and_approve_business()

    branch = _create_branch(business_id, owner_token)

    assert branch["approval_status"] == "Pending"
    assert branch["is_active"] is False
    assert branch["business_id"] == business_id

    db = SessionLocal()
    try:
        audit_entry = db.query(AuditLog).filter(
            AuditLog.entity_type == "Branch",
            AuditLog.entity_id == branch["id"],
            AuditLog.action == "BRANCH_CREATED",
        ).first()
        assert audit_entry is not None
    finally:
        db.close()


def test_branch_creation_fails_when_business_not_active():
    unique = uuid.uuid4().hex[:8]
    owner_username = f"pendingowner_{unique}"
    business = _register_business(username=owner_username, email=f"{unique}@example.com")
    owner_token = _login(owner_username)

    response = client.post(
        f"/api/v1/businesses/{business['id']}/branches",
        json={
            "branch_name": "Should Fail",
            "country_id": _country_id(),
        },
        headers=_auth(owner_token),
    )
    assert response.status_code == 409


def test_non_owner_cannot_create_branch_for_business():
    business_id, _, _ = _register_and_approve_business()

    unique = uuid.uuid4().hex[:8]
    other_username = f"notowner_{unique}"
    _register_business(username=other_username, email=f"{unique}@example.com")
    other_token = _login(other_username)

    response = client.post(
        f"/api/v1/businesses/{business_id}/branches",
        json={"branch_name": "Intruder Branch", "country_id": _country_id()},
        headers=_auth(other_token),
    )
    assert response.status_code == 403


def test_business_owner_sees_all_branches_regardless_of_status():
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_branch(business_id, owner_token)

    response = client.get(
        f"/api/v1/businesses/{business_id}/branches",
        headers=_auth(owner_token),
    )
    assert response.status_code == 200
    ids = [b["id"] for b in response.json()]
    assert branch["id"] in ids


def test_owner_of_another_business_cannot_access_or_modify_branch():
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_branch(business_id, owner_token)

    other_business_id, _, other_owner_token = _register_and_approve_business()

    get_response = client.get(
        f"/api/v1/branches/{branch['id']}",
        headers=_auth(other_owner_token),
    )
    assert get_response.status_code == 403

    update_response = client.patch(
        f"/api/v1/branches/{branch['id']}",
        json={"branch_name": "Hijacked"},
        headers=_auth(other_owner_token),
    )
    assert update_response.status_code == 403


# -----------------------------
# Platform Admin approval
# -----------------------------

def test_platform_admin_can_approve_branch_sets_approval_status_only():
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_branch(business_id, owner_token)

    unique = uuid.uuid4().hex[:8]
    admin_username = f"approver_{unique}"
    _register_business(username=admin_username, email=f"{admin_username}@example.com")
    _promote_to_platform_admin(admin_username)
    admin_token = _login(admin_username)

    response = client.post(
        f"/api/v1/branches/{branch['id']}/approve",
        headers=_auth(admin_token),
    )
    assert response.status_code == 200, response.text

    data = response.json()
    assert data["approval_status"] == "Approved"
    assert data["is_active"] is False
    assert data["approved_by"] is not None

    db = SessionLocal()
    try:
        audit_entry = db.query(AuditLog).filter(
            AuditLog.entity_type == "Branch",
            AuditLog.entity_id == branch["id"],
            AuditLog.action == "BRANCH_APPROVED",
        ).first()
        assert audit_entry is not None
    finally:
        db.close()


def test_platform_admin_can_reject_branch_with_reason():
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_branch(business_id, owner_token)

    unique = uuid.uuid4().hex[:8]
    admin_username = f"rejector_{unique}"
    _register_business(username=admin_username, email=f"{admin_username}@example.com")
    _promote_to_platform_admin(admin_username)
    admin_token = _login(admin_username)

    response = client.post(
        f"/api/v1/branches/{branch['id']}/reject",
        json={"reason": "Incomplete address"},
        headers=_auth(admin_token),
    )
    assert response.status_code == 200, response.text
    assert response.json()["approval_status"] == "Rejected"

    db = SessionLocal()
    try:
        audit_entry = db.query(AuditLog).filter(
            AuditLog.entity_type == "Branch",
            AuditLog.entity_id == branch["id"],
            AuditLog.action == "BRANCH_REJECTED",
        ).first()
        assert audit_entry is not None
        assert audit_entry.reason == "Incomplete address"
    finally:
        db.close()


def test_non_admin_cannot_approve_or_reject_branch():
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_branch(business_id, owner_token)

    response = client.post(
        f"/api/v1/branches/{branch['id']}/approve",
        headers=_auth(owner_token),
    )
    assert response.status_code == 403


def test_cannot_approve_branch_that_is_not_pending():
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_branch(business_id, owner_token)

    unique = uuid.uuid4().hex[:8]
    admin_username = f"repeatadmin_{unique}"
    _register_business(username=admin_username, email=f"{admin_username}@example.com")
    _promote_to_platform_admin(admin_username)
    admin_token = _login(admin_username)

    first = client.post(f"/api/v1/branches/{branch['id']}/approve", headers=_auth(admin_token))
    assert first.status_code == 200

    second = client.post(f"/api/v1/branches/{branch['id']}/approve", headers=_auth(admin_token))
    assert second.status_code == 409


# -----------------------------
# Activation / deactivation
# -----------------------------

def _approve_branch(branch_id):
    unique = uuid.uuid4().hex[:8]
    admin_username = f"activator_{unique}"
    _register_business(username=admin_username, email=f"{admin_username}@example.com")
    _promote_to_platform_admin(admin_username)
    admin_token = _login(admin_username)
    response = client.post(f"/api/v1/branches/{branch_id}/approve", headers=_auth(admin_token))
    assert response.status_code == 200
    return response.json()


def test_cannot_activate_branch_that_is_not_approved():
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_branch(business_id, owner_token)

    response = client.post(f"/api/v1/branches/{branch['id']}/activate", headers=_auth(owner_token))
    assert response.status_code == 409


def test_business_owner_can_activate_approved_branch():
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_branch(business_id, owner_token)
    _approve_branch(branch["id"])

    response = client.post(f"/api/v1/branches/{branch['id']}/activate", headers=_auth(owner_token))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["is_active"] is True
    assert data["approval_status"] == "Approved"

    db = SessionLocal()
    try:
        audit_entry = db.query(AuditLog).filter(
            AuditLog.entity_type == "Branch",
            AuditLog.entity_id == branch["id"],
            AuditLog.action == "BRANCH_ACTIVATED",
        ).first()
        assert audit_entry is not None
    finally:
        db.close()


def test_business_owner_can_deactivate_active_branch_without_losing_approval():
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_branch(business_id, owner_token)
    _approve_branch(branch["id"])

    activate = client.post(f"/api/v1/branches/{branch['id']}/activate", headers=_auth(owner_token))
    assert activate.status_code == 200

    deactivate = client.post(f"/api/v1/branches/{branch['id']}/deactivate", headers=_auth(owner_token))
    assert deactivate.status_code == 200, deactivate.text
    data = deactivate.json()
    assert data["is_active"] is False
    assert data["approval_status"] == "Approved"  # approval history preserved

    db = SessionLocal()
    try:
        audit_entry = db.query(AuditLog).filter(
            AuditLog.entity_type == "Branch",
            AuditLog.entity_id == branch["id"],
            AuditLog.action == "BRANCH_DEACTIVATED",
        ).first()
        assert audit_entry is not None
    finally:
        db.close()


# -----------------------------
# Update
# -----------------------------

def test_business_owner_can_update_branch_profile():
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_branch(business_id, owner_token)

    response = client.patch(
        f"/api/v1/branches/{branch['id']}",
        json={"branch_name": "Renamed Branch", "city": "New City"},
        headers=_auth(owner_token),
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["branch_name"] == "Renamed Branch"
    assert data["city"] == "New City"

    db = SessionLocal()
    try:
        audit_entry = db.query(AuditLog).filter(
            AuditLog.entity_type == "Branch",
            AuditLog.entity_id == branch["id"],
            AuditLog.action == "BRANCH_UPDATED",
        ).first()
        assert audit_entry is not None
    finally:
        db.close()


# -----------------------------
# Working hours
# -----------------------------

def test_business_owner_can_set_and_retrieve_working_hours():
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_branch(business_id, owner_token)

    payload = {
        "hours": [
            {"weekday": 0, "opening_time": "09:00:00", "closing_time": "17:00:00", "is_closed": False},
            {"weekday": 6, "opening_time": None, "closing_time": None, "is_closed": True},
        ]
    }

    put_response = client.put(
        f"/api/v1/branches/{branch['id']}/working-hours",
        json=payload,
        headers=_auth(owner_token),
    )
    assert put_response.status_code == 200, put_response.text
    rows = put_response.json()
    assert len(rows) == 2

    get_response = client.get(
        f"/api/v1/branches/{branch['id']}/working-hours",
        headers=_auth(owner_token),
    )
    assert get_response.status_code == 200
    weekdays = {row["weekday"] for row in get_response.json()}
    assert weekdays == {0, 6}

    db = SessionLocal()
    try:
        audit_entry = db.query(AuditLog).filter(
            AuditLog.entity_type == "Branch",
            AuditLog.entity_id == branch["id"],
            AuditLog.action == "BRANCH_WORKING_HOURS_UPDATED",
        ).first()
        assert audit_entry is not None

        stored = db.query(BranchWorkingHours).filter(BranchWorkingHours.branch_id == branch["id"]).all()
        assert len(stored) == 2
    finally:
        db.close()
