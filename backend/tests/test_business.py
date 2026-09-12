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
        "password": "Testpass123!",
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


def _login(username, password="Testpass123!"):
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
    active_ids = [b["id"] for b in response.json()["items"]]
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


# -----------------------------
# Platform Admin suspend / reactivate (M9 Phase 1)
# -----------------------------

def _register_and_activate_business():
    target = _register_business()
    assert target.status_code == 200
    business_id = target.json()["id"]

    unique = uuid.uuid4().hex[:8]
    admin_username = f"suspadmin_{unique}"
    _register_business(username=admin_username, email=f"{admin_username}@example.com")
    _promote_to_platform_admin(admin_username)
    admin_token = _login(admin_username)

    approve = client.post(
        f"/api/v1/businesses/{business_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert approve.status_code == 200

    return business_id, admin_token


def test_platform_admin_can_suspend_active_business_and_audit_is_recorded():
    business_id, admin_token = _register_and_activate_business()

    response = client.post(
        f"/api/v1/businesses/{business_id}/suspend",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "Suspended"

    db = SessionLocal()
    try:
        audit_entry = db.query(AuditLog).filter(
            AuditLog.entity_type == "Business",
            AuditLog.entity_id == business_id,
            AuditLog.action == "BUSINESS_SUSPENDED",
        ).first()
        assert audit_entry is not None
        assert audit_entry.previous_value == "status=Active"
        assert audit_entry.new_value == "status=Suspended"
    finally:
        db.close()


def test_cannot_suspend_a_business_that_is_not_active():
    unique = uuid.uuid4().hex[:8]
    admin_username = f"suspadmin2_{unique}"

    target = _register_business()
    business_id = target.json()["id"]

    _register_business(username=admin_username, email=f"{admin_username}@example.com")
    _promote_to_platform_admin(admin_username)
    admin_token = _login(admin_username)

    response = client.post(
        f"/api/v1/businesses/{business_id}/suspend",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 409


def test_platform_admin_can_reactivate_suspended_business_and_audit_is_recorded():
    business_id, admin_token = _register_and_activate_business()

    suspend = client.post(
        f"/api/v1/businesses/{business_id}/suspend",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert suspend.status_code == 200

    response = client.post(
        f"/api/v1/businesses/{business_id}/reactivate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "Active"

    db = SessionLocal()
    try:
        audit_entry = db.query(AuditLog).filter(
            AuditLog.entity_type == "Business",
            AuditLog.entity_id == business_id,
            AuditLog.action == "BUSINESS_REACTIVATED",
        ).first()
        assert audit_entry is not None
        assert audit_entry.previous_value == "status=Suspended"
        assert audit_entry.new_value == "status=Active"
    finally:
        db.close()


def test_cannot_reactivate_a_business_that_is_not_suspended():
    business_id, admin_token = _register_and_activate_business()

    response = client.post(
        f"/api/v1/businesses/{business_id}/reactivate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 409


def test_non_admin_cannot_suspend_or_reactivate_business():
    business_id, admin_token = _register_and_activate_business()

    unique = uuid.uuid4().hex[:8]
    other_username = f"nonadminsusp_{unique}"
    _register_business(username=other_username, email=f"{unique}@example.com")
    token = _login(other_username)

    suspend_response = client.post(
        f"/api/v1/businesses/{business_id}/suspend",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert suspend_response.status_code == 403

    suspend = client.post(
        f"/api/v1/businesses/{business_id}/suspend",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert suspend.status_code == 200

    reactivate_response = client.post(
        f"/api/v1/businesses/{business_id}/reactivate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert reactivate_response.status_code == 403


# -----------------------------
# Business Category admin CRUD (M9 Phase 1)
# -----------------------------

def _admin_token():
    unique = uuid.uuid4().hex[:8]
    admin_username = f"catadmin_{unique}"
    _register_business(username=admin_username, email=f"{admin_username}@example.com")
    _promote_to_platform_admin(admin_username)
    return _login(admin_username)


def test_platform_admin_can_create_business_category():
    admin_token = _admin_token()
    unique = uuid.uuid4().hex[:8]

    response = client.post(
        "/api/v1/businesses/categories",
        json={"name": f"Category {unique}", "description": "A test category"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["is_active"] is True

    db = SessionLocal()
    try:
        audit_entry = db.query(AuditLog).filter(
            AuditLog.entity_type == "BusinessCategory",
            AuditLog.entity_id == data["id"],
            AuditLog.action == "BUSINESS_CATEGORY_CREATED",
        ).first()
        assert audit_entry is not None
    finally:
        db.close()


def test_duplicate_business_category_name_is_rejected():
    admin_token = _admin_token()
    unique = uuid.uuid4().hex[:8]
    name = f"Duplicate {unique}"

    first = client.post(
        "/api/v1/businesses/categories",
        json={"name": name},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert first.status_code == 200

    second = client.post(
        "/api/v1/businesses/categories",
        json={"name": name},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert second.status_code == 409


def test_platform_admin_can_update_and_deactivate_business_category():
    admin_token = _admin_token()
    unique = uuid.uuid4().hex[:8]

    created = client.post(
        "/api/v1/businesses/categories",
        json={"name": f"ToUpdate {unique}"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    category_id = created.json()["id"]

    response = client.patch(
        f"/api/v1/businesses/categories/{category_id}",
        json={"description": "Updated description", "is_active": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["description"] == "Updated description"
    assert data["is_active"] is False

    db = SessionLocal()
    try:
        audit_entry = db.query(AuditLog).filter(
            AuditLog.entity_type == "BusinessCategory",
            AuditLog.entity_id == category_id,
            AuditLog.action == "BUSINESS_CATEGORY_UPDATED",
        ).first()
        assert audit_entry is not None
    finally:
        db.close()


def test_deactivated_category_excluded_from_public_list_but_included_in_admin_list():
    admin_token = _admin_token()
    unique = uuid.uuid4().hex[:8]

    created = client.post(
        "/api/v1/businesses/categories",
        json={"name": f"HideMe {unique}"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    category_id = created.json()["id"]

    client.patch(
        f"/api/v1/businesses/categories/{category_id}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    public_list = client.get("/api/v1/businesses/categories")
    assert category_id not in [c["id"] for c in public_list.json()]

    admin_list = client.get(
        "/api/v1/businesses/categories/admin",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_list.status_code == 200
    assert category_id in [c["id"] for c in admin_list.json()]


def test_non_admin_cannot_manage_business_categories():
    unique = uuid.uuid4().hex[:8]
    other_username = f"nonadmincat_{unique}"
    _register_business(username=other_username, email=f"{unique}@example.com")
    token = _login(other_username)

    create_response = client.post(
        "/api/v1/businesses/categories",
        json={"name": f"Forbidden {unique}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 403

    admin_list_response = client.get(
        "/api/v1/businesses/categories/admin",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert admin_list_response.status_code == 403


# -----------------------------
# Business Profile (M9 Phase 6, PRD §72)
# -----------------------------

def test_owner_can_view_and_update_business_profile():
    unique = uuid.uuid4().hex[:8]
    username = f"profileowner_{unique}"
    reg = _register_business(username=username, email=f"{username}@example.com")
    business_id = reg.json()["id"]
    owner_token = _login(username)

    view = client.get(f"/api/v1/businesses/{business_id}", headers={"Authorization": f"Bearer {owner_token}"})
    assert view.status_code == 200, view.text
    assert view.json()["id"] == business_id

    update = client.patch(
        f"/api/v1/businesses/{business_id}",
        json={"business_name": f"Renamed Business {unique}"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert update.status_code == 200, update.text
    assert update.json()["business_name"] == f"Renamed Business {unique}"

    db = SessionLocal()
    try:
        audit_entry = db.query(AuditLog).filter(
            AuditLog.entity_type == "Business",
            AuditLog.entity_id == business_id,
            AuditLog.action == "BUSINESS_PROFILE_UPDATED",
        ).first()
        assert audit_entry is not None
    finally:
        db.close()


def test_non_owner_cannot_view_or_update_business_profile():
    unique = uuid.uuid4().hex[:8]
    target_reg = _register_business()
    target_business_id = target_reg.json()["id"]

    other_username = f"profileother_{unique}"
    _register_business(username=other_username, email=f"{other_username}@example.com")
    other_token = _login(other_username)

    view = client.get(
        f"/api/v1/businesses/{target_business_id}", headers={"Authorization": f"Bearer {other_token}"}
    )
    assert view.status_code == 403

    update = client.patch(
        f"/api/v1/businesses/{target_business_id}",
        json={"business_name": "Hijacked"},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert update.status_code == 403
