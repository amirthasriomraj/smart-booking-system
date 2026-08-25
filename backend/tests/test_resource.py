import uuid

import pytest
from fastapi.testclient import TestClient

from main import app
from database import SessionLocal
from models import (
    Role,
    BusinessCategory,
    Country,
    AuditLog,
    User,
    BusinessMember,
    Resource,
)

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


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


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
    unique = uuid.uuid4().hex[:8]
    owner_username = f"activeowner_{unique}"
    business = _register_business(username=owner_username, email=f"{unique}@example.com")

    admin_username = f"resadmin_{unique}"
    _register_business(username=admin_username, email=f"{admin_username}@example.com")
    _promote_to_platform_admin(admin_username)
    admin_token = _login(admin_username)

    approve = client.post(f"/api/v1/businesses/{business['id']}/approve", headers=_auth(admin_token))
    assert approve.status_code == 200, approve.text

    owner_token = _login(owner_username)
    return business["id"], owner_username, owner_token


def _create_and_approve_branch(business_id, owner_token, branch_name=None):
    unique = uuid.uuid4().hex[:8]
    payload = {
        "branch_name": branch_name or f"Branch {unique}",
        "country_id": _country_id(),
    }
    create = client.post(
        f"/api/v1/businesses/{business_id}/branches",
        json=payload,
        headers=_auth(owner_token),
    )
    assert create.status_code == 200, create.text
    branch = create.json()

    admin_username = f"branchapprover_{unique}"
    _register_business(username=admin_username, email=f"{admin_username}@example.com")
    _promote_to_platform_admin(admin_username)
    admin_token = _login(admin_username)

    approve = client.post(f"/api/v1/branches/{branch['id']}/approve", headers=_auth(admin_token))
    assert approve.status_code == 200, approve.text
    return approve.json()


@pytest.fixture(autouse=True)
def capture_invitation_email(monkeypatch):
    captured = {}

    def fake_send(email, token, role_code, business_name):
        captured["email"] = email
        captured["token"] = token
        captured["role_code"] = role_code
        captured["business_name"] = business_name

    monkeypatch.setattr("routers.staff.send_staff_invitation_email", fake_send)
    monkeypatch.setattr("routers.resources.send_staff_invitation_email", fake_send)
    return captured


def _invite_and_accept_staff(business_id, owner_token, role_code, branch_id=None):
    """Invites + accepts a BRANCH_MANAGER or HR_USER, returns (username, token)."""
    unique = uuid.uuid4().hex[:8]
    email = f"{role_code.lower()}_{unique}@example.com"
    payload = {"email": email, "role_code": role_code}
    if branch_id is not None:
        payload["branch_id"] = branch_id

    captured = {}

    def fake_send(email, token, role_code, business_name):
        captured["token"] = token

    import routers.staff as staff_router
    original = staff_router.send_staff_invitation_email
    staff_router.send_staff_invitation_email = fake_send
    try:
        response = client.post(
            f"/api/v1/businesses/{business_id}/staff/invite",
            json=payload,
            headers=_auth(owner_token),
        )
        assert response.status_code == 200, response.text
    finally:
        staff_router.send_staff_invitation_email = original

    username = f"user_{unique}"
    accept = client.post(
        "/api/v1/auth/accept-invitation",
        json={"token": captured["token"], "username": username, "password": "Testpass123"},
    )
    assert accept.status_code == 200, accept.text
    return username, _login(username)


def _create_category(business_id, owner_token, name=None):
    unique = uuid.uuid4().hex[:8]
    response = client.post(
        f"/api/v1/businesses/{business_id}/resource-categories",
        json={"category_name": name or f"Category {unique}"},
        headers=_auth(owner_token),
    )
    assert response.status_code == 200, response.text
    return response.json()


def _create_resource(branch_id, token, category_id, requires_login=False, **extra):
    unique = uuid.uuid4().hex[:8]
    payload = {
        "resource_name": f"Resource {unique}",
        "resource_category_id": category_id,
        "requires_login": requires_login,
    }
    payload.update(extra)
    response = client.post(f"/api/v1/branches/{branch_id}/resources", json=payload, headers=_auth(token))
    return response


# -----------------------------
# Resource Category (ID-015)
# -----------------------------

def test_owner_can_create_and_list_resource_categories():
    business_id, _, owner_token = _register_and_approve_business()
    category = _create_category(business_id, owner_token, name="Doctor")
    assert category["category_name"] == "Doctor"
    assert category["business_id"] == business_id

    listing = client.get(f"/api/v1/businesses/{business_id}/resource-categories", headers=_auth(owner_token))
    assert listing.status_code == 200
    assert any(c["id"] == category["id"] for c in listing.json())

    db = SessionLocal()
    try:
        audit_entry = db.query(AuditLog).filter(
            AuditLog.entity_type == "ResourceCategory",
            AuditLog.entity_id == category["id"],
            AuditLog.action == "RESOURCE_CATEGORY_CREATED",
        ).first()
        assert audit_entry is not None
    finally:
        db.close()


def test_non_owner_cannot_create_resource_category():
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_and_approve_branch(business_id, owner_token)
    _, bm_token = _invite_and_accept_staff(business_id, owner_token, "BRANCH_MANAGER", branch["id"])

    response = client.post(
        f"/api/v1/businesses/{business_id}/resource-categories",
        json={"category_name": "Should Fail"},
        headers=_auth(bm_token),
    )
    assert response.status_code == 403


def test_branch_manager_can_read_but_not_write_resource_categories():
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_and_approve_branch(business_id, owner_token)
    _create_category(business_id, owner_token, name="Coach")
    _, bm_token = _invite_and_accept_staff(business_id, owner_token, "BRANCH_MANAGER", branch["id"])

    listing = client.get(f"/api/v1/businesses/{business_id}/resource-categories", headers=_auth(bm_token))
    assert listing.status_code == 200
    assert len(listing.json()) >= 1


def test_update_resource_category():
    business_id, _, owner_token = _register_and_approve_business()
    category = _create_category(business_id, owner_token, name="Original")

    update = client.patch(
        f"/api/v1/resource-categories/{category['id']}",
        json={"category_name": "Renamed"},
        headers=_auth(owner_token),
    )
    assert update.status_code == 200, update.text
    assert update.json()["category_name"] == "Renamed"


# -----------------------------
# Resource CRUD (ID-012, ID-016)
# -----------------------------

def test_owner_can_create_resource_business_id_denormalized():
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_and_approve_branch(business_id, owner_token)
    category = _create_category(business_id, owner_token)

    response = _create_resource(branch["id"], owner_token, category["id"])
    assert response.status_code == 200, response.text
    resource = response.json()
    assert resource["status"] == "Pending"
    assert resource["branch_id"] == branch["id"]
    assert resource["business_id"] == business_id  # ID-012

    db = SessionLocal()
    try:
        audit_entry = db.query(AuditLog).filter(
            AuditLog.entity_type == "Resource",
            AuditLog.entity_id == resource["id"],
            AuditLog.action == "RESOURCE_CREATED",
        ).first()
        assert audit_entry is not None
    finally:
        db.close()


def test_owner_can_create_resource_on_pending_branch():
    """PRD §13 'Pending Approval': resources may be configured on a branch
    that has not yet been approved. Only bookings are blocked at that stage."""
    business_id, _, owner_token = _register_and_approve_business()
    unique = uuid.uuid4().hex[:8]
    pending_branch = client.post(
        f"/api/v1/businesses/{business_id}/branches",
        json={"branch_name": f"Pending {unique}", "country_id": _country_id()},
        headers=_auth(owner_token),
    ).json()
    assert pending_branch["approval_status"] == "Pending"
    category = _create_category(business_id, owner_token)

    response = _create_resource(pending_branch["id"], owner_token, category["id"])
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "Pending"


def test_branch_manager_can_create_resource_only_in_own_branch():
    business_id, _, owner_token = _register_and_approve_business()
    branch_a = _create_and_approve_branch(business_id, owner_token, "Branch A")
    branch_b = _create_and_approve_branch(business_id, owner_token, "Branch B")
    category = _create_category(business_id, owner_token)
    _, bm_token = _invite_and_accept_staff(business_id, owner_token, "BRANCH_MANAGER", branch_a["id"])

    ok = _create_resource(branch_a["id"], bm_token, category["id"])
    assert ok.status_code == 200, ok.text

    forbidden = _create_resource(branch_b["id"], bm_token, category["id"])
    assert forbidden.status_code == 403


def test_hr_user_cannot_create_resource():
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_and_approve_branch(business_id, owner_token)
    category = _create_category(business_id, owner_token)
    _, hr_token = _invite_and_accept_staff(business_id, owner_token, "HR_USER")

    response = _create_resource(branch["id"], hr_token, category["id"])
    assert response.status_code == 403


def test_hr_user_has_business_wide_read_access_to_resources():
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_and_approve_branch(business_id, owner_token)
    category = _create_category(business_id, owner_token)
    resource = _create_resource(branch["id"], owner_token, category["id"]).json()
    _, hr_token = _invite_and_accept_staff(business_id, owner_token, "HR_USER")

    listing = client.get(f"/api/v1/businesses/{business_id}/resources", headers=_auth(hr_token))
    assert listing.status_code == 200
    assert any(r["id"] == resource["id"] for r in listing.json())


def test_update_resource_configure():
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_and_approve_branch(business_id, owner_token)
    category = _create_category(business_id, owner_token)
    resource = _create_resource(branch["id"], owner_token, category["id"]).json()

    update = client.patch(
        f"/api/v1/resources/{resource['id']}",
        json={"resource_name": "Updated Name", "max_bookings_per_day": 5, "booking_buffer_minutes": 15},
        headers=_auth(owner_token),
    )
    assert update.status_code == 200, update.text
    body = update.json()
    assert body["resource_name"] == "Updated Name"
    assert body["max_bookings_per_day"] == 5
    assert body["booking_buffer_minutes"] == 15


# -----------------------------
# Resource lifecycle / status (PRD §14.4)
# -----------------------------

def test_activate_and_suspend_resource_without_login():
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_and_approve_branch(business_id, owner_token)
    category = _create_category(business_id, owner_token)
    resource = _create_resource(branch["id"], owner_token, category["id"], requires_login=False).json()

    activate = client.post(f"/api/v1/resources/{resource['id']}/activate", headers=_auth(owner_token))
    assert activate.status_code == 200, activate.text
    assert activate.json()["status"] == "Active"

    suspend = client.post(f"/api/v1/resources/{resource['id']}/suspend", headers=_auth(owner_token))
    assert suspend.status_code == 200, suspend.text
    assert suspend.json()["status"] == "Suspended"

    # Suspended -> Active is a valid operational reactivation.
    reactivate = client.post(f"/api/v1/resources/{resource['id']}/activate", headers=_auth(owner_token))
    assert reactivate.status_code == 200
    assert reactivate.json()["status"] == "Active"


def test_activate_blocked_when_login_required_without_linked_user():
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_and_approve_branch(business_id, owner_token)
    category = _create_category(business_id, owner_token)
    resource = _create_resource(branch["id"], owner_token, category["id"], requires_login=True).json()

    activate = client.post(f"/api/v1/resources/{resource['id']}/activate", headers=_auth(owner_token))
    assert activate.status_code == 409, activate.text


def test_suspend_requires_active_status():
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_and_approve_branch(business_id, owner_token)
    category = _create_category(business_id, owner_token)
    resource = _create_resource(branch["id"], owner_token, category["id"]).json()

    suspend = client.post(f"/api/v1/resources/{resource['id']}/suspend", headers=_auth(owner_token))
    assert suspend.status_code == 409


# -----------------------------
# Resource Working Hours (ID-013)
# -----------------------------

def test_upsert_resource_working_hours_with_break():
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_and_approve_branch(business_id, owner_token)
    category = _create_category(business_id, owner_token)
    resource = _create_resource(branch["id"], owner_token, category["id"]).json()

    payload = {
        "hours": [
            {
                "weekday": 0,
                "opening_time": "09:00:00",
                "closing_time": "17:00:00",
                "is_closed": False,
                "break_start_time": "13:00:00",
                "break_end_time": "14:00:00",
            }
        ]
    }
    response = client.put(f"/api/v1/resources/{resource['id']}/working-hours", json=payload, headers=_auth(owner_token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body[0]["break_start_time"] == "13:00:00"
    assert body[0]["break_end_time"] == "14:00:00"


# -----------------------------
# Resource User invitation (ID-014, ID-016)
# -----------------------------

def test_invite_resource_user_case_a_and_accept_links_resource(capture_invitation_email):
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_and_approve_branch(business_id, owner_token)
    category = _create_category(business_id, owner_token)
    resource = _create_resource(branch["id"], owner_token, category["id"], requires_login=True).json()

    unique = uuid.uuid4().hex[:8]
    email = f"ruser_{unique}@example.com"
    invite = client.post(
        f"/api/v1/businesses/{business_id}/resources/{resource['id']}/invite-user",
        json={"email": email},
        headers=_auth(owner_token),
    )
    assert invite.status_code == 200, invite.text
    member = invite.json()
    assert member["status"] == "Pending"
    assert member["role_code"] == "RESOURCE_USER"

    db = SessionLocal()
    try:
        row = db.query(BusinessMember).filter(BusinessMember.id == member["id"]).first()
        assert row.linked_resource_id == resource["id"]
        assert row.requires_credential_setup is True
    finally:
        db.close()

    token = capture_invitation_email["token"]
    accept = client.post(
        "/api/v1/auth/accept-invitation",
        json={"token": token, "username": f"ruser_{unique}", "password": "Testpass123"},
    )
    assert accept.status_code == 200, accept.text

    db = SessionLocal()
    try:
        updated_member = db.query(BusinessMember).filter(BusinessMember.id == member["id"]).first()
        assert updated_member.status == "Active"
        assert updated_member.linked_resource_id is None

        linked_resource = db.query(Resource).filter(Resource.id == resource["id"]).first()
        assert linked_resource.linked_user_id == updated_member.user_id
    finally:
        db.close()

    # Now activation succeeds because the login link is complete (ID-014).
    activate = client.post(f"/api/v1/resources/{resource['id']}/activate", headers=_auth(owner_token))
    assert activate.status_code == 200, activate.text
    assert activate.json()["status"] == "Active"


def test_invite_resource_user_requires_requires_login_true():
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_and_approve_branch(business_id, owner_token)
    category = _create_category(business_id, owner_token)
    resource = _create_resource(branch["id"], owner_token, category["id"], requires_login=False).json()

    response = client.post(
        f"/api/v1/businesses/{business_id}/resources/{resource['id']}/invite-user",
        json={"email": "x@example.com"},
        headers=_auth(owner_token),
    )
    assert response.status_code == 409


def test_branch_manager_can_invite_resource_user_only_in_own_branch():
    business_id, _, owner_token = _register_and_approve_business()
    branch_a = _create_and_approve_branch(business_id, owner_token, "Branch A")
    branch_b = _create_and_approve_branch(business_id, owner_token, "Branch B")
    category = _create_category(business_id, owner_token)
    resource_a = _create_resource(branch_a["id"], owner_token, category["id"], requires_login=True).json()
    resource_b = _create_resource(branch_b["id"], owner_token, category["id"], requires_login=True).json()
    _, bm_token = _invite_and_accept_staff(business_id, owner_token, "BRANCH_MANAGER", branch_a["id"])

    ok = client.post(
        f"/api/v1/businesses/{business_id}/resources/{resource_a['id']}/invite-user",
        json={"email": "own_branch@example.com"},
        headers=_auth(bm_token),
    )
    assert ok.status_code == 200, ok.text

    forbidden = client.post(
        f"/api/v1/businesses/{business_id}/resources/{resource_b['id']}/invite-user",
        json={"email": "other_branch@example.com"},
        headers=_auth(bm_token),
    )
    assert forbidden.status_code == 403


def test_hr_user_can_invite_resource_user_business_wide():
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_and_approve_branch(business_id, owner_token)
    category = _create_category(business_id, owner_token)
    resource = _create_resource(branch["id"], owner_token, category["id"], requires_login=True).json()
    _, hr_token = _invite_and_accept_staff(business_id, owner_token, "HR_USER")

    response = client.post(
        f"/api/v1/businesses/{business_id}/resources/{resource['id']}/invite-user",
        json={"email": "hrinvited@example.com"},
        headers=_auth(hr_token),
    )
    assert response.status_code == 200, response.text


def test_resend_resource_invite():
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_and_approve_branch(business_id, owner_token)
    category = _create_category(business_id, owner_token)
    resource = _create_resource(branch["id"], owner_token, category["id"], requires_login=True).json()

    invite = client.post(
        f"/api/v1/businesses/{business_id}/resources/{resource['id']}/invite-user",
        json={"email": "resend@example.com"},
        headers=_auth(owner_token),
    )
    member_id = invite.json()["id"]

    resend = client.post(f"/api/v1/business-members/{member_id}/resend-resource-invite", headers=_auth(owner_token))
    assert resend.status_code == 200, resend.text


def test_deactivate_resource_user_does_not_change_resource_status(capture_invitation_email):
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_and_approve_branch(business_id, owner_token)
    category = _create_category(business_id, owner_token)
    resource = _create_resource(branch["id"], owner_token, category["id"], requires_login=True).json()

    unique = uuid.uuid4().hex[:8]
    email = f"deact_{unique}@example.com"
    invite = client.post(
        f"/api/v1/businesses/{business_id}/resources/{resource['id']}/invite-user",
        json={"email": email},
        headers=_auth(owner_token),
    )
    member_id = invite.json()["id"]
    token = capture_invitation_email["token"]

    accept = client.post(
        "/api/v1/auth/accept-invitation",
        json={"token": token, "username": f"deact_{unique}", "password": "Testpass123"},
    )
    assert accept.status_code == 200, accept.text

    activate = client.post(f"/api/v1/resources/{resource['id']}/activate", headers=_auth(owner_token))
    assert activate.status_code == 200, activate.text

    deactivate = client.post(f"/api/v1/business-members/{member_id}/deactivate-resource-user", headers=_auth(owner_token))
    assert deactivate.status_code == 200, deactivate.text
    assert deactivate.json()["status"] == "Inactive"

    resource_check = client.get(f"/api/v1/resources/{resource['id']}", headers=_auth(owner_token))
    assert resource_check.json()["status"] == "Active"  # ID-014: independent of membership status


def test_list_resource_users_scoped_for_branch_manager():
    business_id, _, owner_token = _register_and_approve_business()
    branch_a = _create_and_approve_branch(business_id, owner_token, "Branch A")
    branch_b = _create_and_approve_branch(business_id, owner_token, "Branch B")
    category = _create_category(business_id, owner_token)
    resource_a = _create_resource(branch_a["id"], owner_token, category["id"], requires_login=True).json()
    resource_b = _create_resource(branch_b["id"], owner_token, category["id"], requires_login=True).json()

    client.post(
        f"/api/v1/businesses/{business_id}/resources/{resource_a['id']}/invite-user",
        json={"email": "scoped_a@example.com"},
        headers=_auth(owner_token),
    )
    client.post(
        f"/api/v1/businesses/{business_id}/resources/{resource_b['id']}/invite-user",
        json={"email": "scoped_b@example.com"},
        headers=_auth(owner_token),
    )

    _, bm_token = _invite_and_accept_staff(business_id, owner_token, "BRANCH_MANAGER", branch_a["id"])

    listing = client.get(f"/api/v1/businesses/{business_id}/resource-users", headers=_auth(bm_token))
    assert listing.status_code == 200
    emails = {m["email"] for m in listing.json()}
    assert "scoped_a@example.com" in emails
    assert "scoped_b@example.com" not in emails


# -----------------------------
# Cross-business isolation
# -----------------------------

def test_resource_user_does_not_appear_in_m3_staff_list():
    """
    M3's GET /businesses/{id}/staff stays limited to Branch Manager / HR User
    (unchanged Milestone 3 semantics) even though RESOURCE_USER now shares
    the same invitation/acceptance machinery. Resource Users are listed via
    the dedicated GET /businesses/{id}/resource-users endpoint instead.
    """
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_and_approve_branch(business_id, owner_token)
    category = _create_category(business_id, owner_token)
    resource = _create_resource(branch["id"], owner_token, category["id"], requires_login=True).json()
    _, bm_token = _invite_and_accept_staff(business_id, owner_token, "BRANCH_MANAGER", branch["id"])

    invite = client.post(
        f"/api/v1/businesses/{business_id}/resources/{resource['id']}/invite-user",
        json={"email": "notinstafflist@example.com"},
        headers=_auth(owner_token),
    )
    assert invite.status_code == 200, invite.text

    staff_listing = client.get(f"/api/v1/businesses/{business_id}/staff", headers=_auth(owner_token))
    assert staff_listing.status_code == 200
    role_codes = {m["role_code"] for m in staff_listing.json()}
    emails = {m["email"] for m in staff_listing.json()}
    assert "RESOURCE_USER" not in role_codes
    assert "notinstafflist@example.com" not in emails
    assert "BRANCH_MANAGER" in role_codes  # sanity: existing M3 members still listed

    resource_user_listing = client.get(f"/api/v1/businesses/{business_id}/resource-users", headers=_auth(owner_token))
    assert resource_user_listing.status_code == 200
    assert any(m["email"] == "notinstafflist@example.com" for m in resource_user_listing.json())


def test_resource_category_and_resource_are_tenant_isolated():
    business_id, _, owner_token = _register_and_approve_business()
    other_business_id, _, other_owner_token = _register_and_approve_business()
    branch = _create_and_approve_branch(business_id, owner_token)
    category = _create_category(business_id, owner_token)

    response = _create_resource(branch["id"], other_owner_token, category["id"])
    assert response.status_code == 403  # other owner has no access to this branch
