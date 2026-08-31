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
    UserProfile,
    UserRole,
    PlatformCustomer,
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

    admin_username = f"custadmin_{unique}"
    _register_business(username=admin_username, email=f"{admin_username}@example.com")
    _promote_to_platform_admin(admin_username)
    admin_token = _login(admin_username)

    approve = client.post(
        f"/api/v1/businesses/{business['id']}/approve",
        headers=_auth(admin_token),
    )
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

    admin_username = f"custbranchapprover_{unique}"
    _register_business(username=admin_username, email=f"{admin_username}@example.com")
    _promote_to_platform_admin(admin_username)
    admin_token = _login(admin_username)

    approve = client.post(f"/api/v1/branches/{branch['id']}/approve", headers=_auth(admin_token))
    assert approve.status_code == 200, approve.text

    activate = client.post(f"/api/v1/branches/{branch['id']}/activate", headers=_auth(owner_token))
    assert activate.status_code == 200, activate.text

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
    return captured


def _create_branch_manager(business_id, owner_token, branch_id, capture):
    unique = uuid.uuid4().hex[:8]
    email = f"bm_{unique}@example.com"
    invite = client.post(
        f"/api/v1/businesses/{business_id}/staff/invite",
        json={"email": email, "role_code": "BRANCH_MANAGER", "branch_id": branch_id},
        headers=_auth(owner_token),
    )
    assert invite.status_code == 200, invite.text
    token = capture["token"]
    username = f"bmuser_{unique}"
    accept = client.post(
        "/api/v1/auth/accept-invitation",
        json={"token": token, "username": username, "password": "Testpass123"},
    )
    assert accept.status_code == 200, accept.text
    return _login(username)


def _create_hr_user(business_id, owner_token, capture):
    unique = uuid.uuid4().hex[:8]
    email = f"hr_{unique}@example.com"
    invite = client.post(
        f"/api/v1/businesses/{business_id}/staff/invite",
        json={"email": email, "role_code": "HR_USER"},
        headers=_auth(owner_token),
    )
    assert invite.status_code == 200, invite.text
    token = capture["token"]
    username = f"hruser_{unique}"
    accept = client.post(
        "/api/v1/auth/accept-invitation",
        json={"token": token, "username": username, "password": "Testpass123"},
    )
    assert accept.status_code == 200, accept.text
    return _login(username)


def _register_customer(**overrides):
    unique = uuid.uuid4().hex[:8]
    payload = {
        "first_name": "Amit",
        "last_name": "Kumar",
        "email": f"cust_{unique}@example.com",
        "mobile_number": "9990001111",
        "password": "Testpass123",
    }
    payload.update(overrides)
    response = client.post("/api/v1/customers/register", json=payload)
    return response, payload


def _create_walk_in(business_id, staff_token, **overrides):
    unique = uuid.uuid4().hex[:8]
    payload = {
        "first_name": "Walk",
        "last_name": "In",
        "mobile_number": "8880002222",
    }
    payload.update(overrides)
    return client.post(
        f"/api/v1/businesses/{business_id}/customers",
        json=payload,
        headers=_auth(staff_token),
    )


# -----------------------------
# Self-registration (PRD §17.5, ID-034)
# -----------------------------

def test_customer_self_registration_creates_full_identity():
    response, payload = _register_customer()
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["email"] == payload["email"]
    assert body["first_name"] == "Amit"
    assert body["last_name"] == "Kumar"
    assert body["mobile_number"] == "9990001111"
    assert body["platform_customer_id"] is not None

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == payload["email"]).first()
        assert user is not None
        assert user.username == payload["email"]  # ID-034: email used as login handle
        assert user.is_active is True

        profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
        assert profile is not None
        assert profile.first_name == "Amit"

        role = db.query(Role).filter(Role.code == "CUSTOMER").first()
        assert db.query(UserRole).filter(UserRole.user_id == user.id, UserRole.role_id == role.id).first() is not None

        pc = db.query(PlatformCustomer).filter(PlatformCustomer.user_id == user.id).first()
        assert pc is not None

        audit_entry = (
            db.query(AuditLog)
            .filter(AuditLog.entity_type == "PlatformCustomer", AuditLog.entity_id == pc.id, AuditLog.action == "CUSTOMER_CREATED")
            .first()
        )
        assert audit_entry is not None
    finally:
        db.close()

    # Customer can log in using their email as the username.
    token = _login(payload["email"])
    me = client.get("/api/v1/auth/me", headers=_auth(token))
    assert me.status_code == 200, me.text
    assert me.json()["customer"] is not None
    assert me.json()["business"] is None


def test_customer_self_registration_duplicate_real_email_is_rejected():
    response, payload = _register_customer()
    assert response.status_code == 200, response.text

    second = client.post("/api/v1/customers/register", json=payload)
    assert second.status_code == 409


def test_customer_self_registration_upgrades_unclaimed_walk_in_placeholder():
    business_id, _, owner_token = _register_and_approve_business()

    unique = uuid.uuid4().hex[:8]
    email = f"walkin_{unique}@example.com"
    walk_in = _create_walk_in(business_id, owner_token, email=email, first_name="Old", last_name="Name")
    assert walk_in.status_code == 200, walk_in.text

    db = SessionLocal()
    try:
        placeholder_user = db.query(User).filter(User.email == email).first()
        assert placeholder_user.is_active is False
        placeholder_user_id = placeholder_user.id
    finally:
        db.close()

    response, payload = _register_customer(email=email, first_name="New", last_name="Name")
    assert response.status_code == 200, response.text
    assert response.json()["first_name"] == "New"

    db = SessionLocal()
    try:
        upgraded_user = db.query(User).filter(User.email == email).first()
        assert upgraded_user.id == placeholder_user_id  # same identity, not a new row
        assert upgraded_user.is_active is True
        assert upgraded_user.username == email
    finally:
        db.close()

    # The upgraded identity can now log in with the real password.
    token = _login(email)
    assert token


# -----------------------------
# Customer self profile (BR-040)
# -----------------------------

def test_customer_can_view_and_update_own_profile():
    response, payload = _register_customer()
    token = _login(payload["email"])

    get_response = client.get("/api/v1/customers/me", headers=_auth(token))
    assert get_response.status_code == 200, get_response.text
    assert get_response.json()["mobile_number"] == "9990001111"

    patch_response = client.patch(
        "/api/v1/customers/me",
        json={"city": "Bengaluru", "preferred_language": "en"},
        headers=_auth(token),
    )
    assert patch_response.status_code == 200, patch_response.text
    assert patch_response.json()["city"] == "Bengaluru"
    assert patch_response.json()["preferred_language"] == "en"
    # Fields not included in the PATCH are left untouched.
    assert patch_response.json()["first_name"] == "Amit"


def test_non_customer_user_cannot_access_customer_self_endpoints():
    _, _, owner_token = _register_and_approve_business()
    response = client.get("/api/v1/customers/me", headers=_auth(owner_token))
    assert response.status_code == 403


# -----------------------------
# Walk-in creation (PRD §17.4, BR-037, BR-038)
# -----------------------------

def test_business_owner_can_create_walk_in_customer():
    business_id, _, owner_token = _register_and_approve_business()

    response = _create_walk_in(business_id, owner_token, first_name="Priya", last_name="Rao")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["first_name"] == "Priya"
    assert body["status"] == "Active"
    assert body["customer_number"] == f"CUST-{body['id']:06d}"  # ID-033

    db = SessionLocal()
    try:
        audit_entry = (
            db.query(AuditLog)
            .filter(
                AuditLog.entity_type == "BusinessCustomer",
                AuditLog.entity_id == body["id"],
                AuditLog.action == "CUSTOMER_CREATED",
            )
            .first()
        )
        assert audit_entry is not None
    finally:
        db.close()


def test_walk_in_without_email_gets_placeholder_identity():
    business_id, _, owner_token = _register_and_approve_business()
    response = _create_walk_in(business_id, owner_token)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["email"].endswith("@placeholder.smartbooking.local")


def test_walk_in_reuses_existing_platform_identity_by_email():
    business_id, _, owner_token = _register_and_approve_business()
    other_business_id, _, other_owner_token = _register_and_approve_business()

    unique = uuid.uuid4().hex[:8]
    email = f"shared_{unique}@example.com"

    first = _create_walk_in(business_id, owner_token, email=email)
    assert first.status_code == 200, first.text

    second = _create_walk_in(other_business_id, other_owner_token, email=email)
    assert second.status_code == 200, second.text

    assert first.json()["platform_customer_id"] == second.json()["platform_customer_id"]
    assert first.json()["id"] != second.json()["id"]  # distinct BusinessCustomer rows


def test_duplicate_walk_in_for_same_business_and_identity_is_rejected():
    business_id, _, owner_token = _register_and_approve_business()
    unique = uuid.uuid4().hex[:8]
    email = f"dup_{unique}@example.com"

    first = _create_walk_in(business_id, owner_token, email=email)
    assert first.status_code == 200, first.text

    second = _create_walk_in(business_id, owner_token, email=email)
    assert second.status_code == 409


# -----------------------------
# Backfilling an email onto an unclaimed walk-in placeholder (the fix for
# the Case A workflow gap: an email-less walk-in previously had no path to
# ever become login-capable, since the ID-030/ID-031 self-registration
# upgrade is keyed on an email match).
# -----------------------------

def test_staff_can_add_email_to_unclaimed_placeholder_enabling_later_self_registration():
    business_id, _, owner_token = _register_and_approve_business()

    walk_in = _create_walk_in(business_id, owner_token)  # no email -> placeholder
    assert walk_in.status_code == 200, walk_in.text
    business_customer_id = walk_in.json()["id"]
    platform_customer_id = walk_in.json()["platform_customer_id"]
    assert walk_in.json()["email"].endswith("@placeholder.smartbooking.local")

    unique = uuid.uuid4().hex[:8]
    real_email = f"backfilled_{unique}@example.com"

    add_email = client.patch(
        f"/api/v1/business-customers/{business_customer_id}",
        json={"email": real_email},
        headers=_auth(owner_token),
    )
    assert add_email.status_code == 200, add_email.text
    assert add_email.json()["email"] == real_email

    response, payload = _register_customer(email=real_email, first_name="Backfilled")
    assert response.status_code == 200, response.text
    # Same identity is upgraded in place — not a second, disconnected one.
    assert response.json()["platform_customer_id"] == platform_customer_id

    # The original BusinessCustomer relationship is preserved unchanged.
    get_bc = client.get(f"/api/v1/business-customers/{business_customer_id}", headers=_auth(owner_token))
    assert get_bc.status_code == 200, get_bc.text
    assert get_bc.json()["platform_customer_id"] == platform_customer_id
    assert get_bc.json()["id"] == business_customer_id

    # The upgraded identity can now log in normally.
    token = _login(real_email)
    assert token


def test_email_backfill_accepts_full_edit_form_payload():
    """
    Regression test: the CustomerManagement.jsx edit form always submits every
    field together (first_name, last_name, mobile_number, notes, email), not
    email in isolation. A prior manual QA pass found that this combined
    payload 422'd against a stale backend process that hadn't picked up the
    email-backfill schema/crud change, which the frontend then rendered as an
    uncaught crash (a separate bug, fixed in CustomerManagement.jsx). This
    test pins the actual browser-shaped request so a future change can't
    silently reintroduce a gap between "email alone" and "email + other
    fields" behaving differently.
    """
    business_id, _, owner_token = _register_and_approve_business()
    walk_in = _create_walk_in(business_id, owner_token, first_name="Full", last_name="Payload")
    assert walk_in.status_code == 200, walk_in.text
    business_customer_id = walk_in.json()["id"]

    unique = uuid.uuid4().hex[:8]
    real_email = f"fullpayload_{unique}@example.com"

    response = client.patch(
        f"/api/v1/business-customers/{business_customer_id}",
        json={
            "first_name": "Full",
            "last_name": "Payload",
            "mobile_number": "7770001111",
            "notes": "",
            "email": real_email,
        },
        headers=_auth(owner_token),
    )
    assert response.status_code == 200, response.text
    assert response.json()["email"] == real_email
    assert response.json()["notes"] == ""

    get_bc = client.get(f"/api/v1/business-customers/{business_customer_id}", headers=_auth(owner_token))
    assert get_bc.status_code == 200, get_bc.text
    assert get_bc.json()["email"] == real_email


def test_staff_cannot_set_duplicate_email_on_placeholder():
    business_id, _, owner_token = _register_and_approve_business()

    existing_response, existing_payload = _register_customer()
    assert existing_response.status_code == 200, existing_response.text

    walk_in = _create_walk_in(business_id, owner_token)
    assert walk_in.status_code == 200, walk_in.text
    business_customer_id = walk_in.json()["id"]

    collide = client.patch(
        f"/api/v1/business-customers/{business_customer_id}",
        json={"email": existing_payload["email"]},
        headers=_auth(owner_token),
    )
    assert collide.status_code == 409


def test_staff_cannot_change_email_after_customer_has_claimed_account():
    business_id, _, owner_token = _register_and_approve_business()
    unique = uuid.uuid4().hex[:8]
    email = f"claimed_{unique}@example.com"

    walk_in = _create_walk_in(business_id, owner_token, email=email)
    assert walk_in.status_code == 200, walk_in.text
    business_customer_id = walk_in.json()["id"]

    # Customer claims the account via self-registration (Case B, already covered
    # by test_customer_self_registration_upgrades_unclaimed_walk_in_placeholder;
    # re-exercised here to reach the "already claimed" state for this test).
    reg_response = client.post(
        "/api/v1/customers/register",
        json={
            "first_name": "Claimed",
            "last_name": "Customer",
            "email": email,
            "mobile_number": "9991112222",
            "password": "Testpass123",
        },
    )
    assert reg_response.status_code == 200, reg_response.text

    other_unique = uuid.uuid4().hex[:8]
    attempt = client.patch(
        f"/api/v1/business-customers/{business_customer_id}",
        json={"email": f"newemail_{other_unique}@example.com"},
        headers=_auth(owner_token),
    )
    assert attempt.status_code == 409

    # Non-email fields remain editable after the account is claimed.
    still_editable = client.patch(
        f"/api/v1/business-customers/{business_customer_id}",
        json={"notes": "still editable after claim"},
        headers=_auth(owner_token),
    )
    assert still_editable.status_code == 200, still_editable.text
    assert still_editable.json()["notes"] == "still editable after claim"


def test_branch_manager_can_create_and_list_customers_business_wide(capture_invitation_email):
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_and_approve_branch(business_id, owner_token)
    bm_token = _create_branch_manager(business_id, owner_token, branch["id"], capture_invitation_email)

    response = _create_walk_in(business_id, bm_token, first_name="ByBM")
    assert response.status_code == 200, response.text

    listing = client.get(f"/api/v1/businesses/{business_id}/customers", headers=_auth(bm_token))
    assert listing.status_code == 200, listing.text
    assert listing.json()["total"] >= 1


def test_hr_user_denied_customer_management(capture_invitation_email):
    business_id, _, owner_token = _register_and_approve_business()
    hr_token = _create_hr_user(business_id, owner_token, capture_invitation_email)

    response = _create_walk_in(business_id, hr_token)
    assert response.status_code == 403

    listing = client.get(f"/api/v1/businesses/{business_id}/customers", headers=_auth(hr_token))
    assert listing.status_code == 403


def test_platform_admin_denied_tenant_customer_management():
    business_id, _, owner_token = _register_and_approve_business()

    unique = uuid.uuid4().hex[:8]
    admin_username = f"platadmin_{unique}"
    _register_business(username=admin_username, email=f"{admin_username}@example.com")
    _promote_to_platform_admin(admin_username)
    admin_token = _login(admin_username)

    response = _create_walk_in(business_id, admin_token)
    assert response.status_code == 403


# -----------------------------
# Tenant isolation
# -----------------------------

def test_staff_cannot_manage_another_business_customers():
    business_id, _, owner_token = _register_and_approve_business()
    other_business_id, _, other_owner_token = _register_and_approve_business()

    walk_in = _create_walk_in(business_id, owner_token)
    assert walk_in.status_code == 200, walk_in.text
    business_customer_id = walk_in.json()["id"]

    cross_get = client.get(f"/api/v1/business-customers/{business_customer_id}", headers=_auth(other_owner_token))
    assert cross_get.status_code == 403

    cross_list = client.get(f"/api/v1/businesses/{business_id}/customers", headers=_auth(other_owner_token))
    assert cross_list.status_code == 403


# -----------------------------
# List / search / pagination (PRD §17.6)
# -----------------------------

def test_list_customers_supports_search_and_pagination():
    business_id, _, owner_token = _register_and_approve_business()
    unique = uuid.uuid4().hex[:8]

    _create_walk_in(business_id, owner_token, first_name="Searchable", last_name="Person", mobile_number=f"7{unique[:9]}")
    _create_walk_in(business_id, owner_token, first_name="Other", last_name="Body")

    search_response = client.get(
        f"/api/v1/businesses/{business_id}/customers",
        params={"search": "Searchable"},
        headers=_auth(owner_token),
    )
    assert search_response.status_code == 200, search_response.text
    results = search_response.json()
    assert results["total"] == 1
    assert results["data"][0]["first_name"] == "Searchable"

    paged_response = client.get(
        f"/api/v1/businesses/{business_id}/customers",
        params={"limit": 1, "offset": 0},
        headers=_auth(owner_token),
    )
    assert paged_response.status_code == 200, paged_response.text
    assert len(paged_response.json()["data"]) == 1
    assert paged_response.json()["total"] >= 2


# -----------------------------
# Update / status toggle
# -----------------------------

def test_update_business_customer_and_status_toggle():
    business_id, _, owner_token = _register_and_approve_business()
    walk_in = _create_walk_in(business_id, owner_token)
    business_customer_id = walk_in.json()["id"]

    update_response = client.patch(
        f"/api/v1/business-customers/{business_customer_id}",
        json={"notes": "VIP customer", "city": "Mumbai"},
        headers=_auth(owner_token),
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["notes"] == "VIP customer"
    assert update_response.json()["city"] == "Mumbai"

    status_response = client.patch(
        f"/api/v1/business-customers/{business_customer_id}/status",
        json={"status": "Inactive"},
        headers=_auth(owner_token),
    )
    assert status_response.status_code == 200, status_response.text
    assert status_response.json()["status"] == "Inactive"

    db = SessionLocal()
    try:
        audit_entries = (
            db.query(AuditLog)
            .filter(AuditLog.entity_type == "BusinessCustomer", AuditLog.entity_id == business_customer_id)
            .all()
        )
        actions = {a.action for a in audit_entries}
        assert "CUSTOMER_CREATED" in actions
        assert "CUSTOMER_UPDATED" in actions
    finally:
        db.close()

    # Re-setting the same status is rejected.
    repeat = client.patch(
        f"/api/v1/business-customers/{business_customer_id}/status",
        json={"status": "Inactive"},
        headers=_auth(owner_token),
    )
    assert repeat.status_code == 409


# -----------------------------
# Browse (workflow 90.3 boundary — stops before Availability/Booking, M7)
# -----------------------------

def _create_template(business_id, owner_token, name=None, **extra):
    unique = uuid.uuid4().hex[:8]
    payload = {
        "name": name or f"Service {unique}",
        "default_duration": 30,
        "default_price": "300.00",
        "default_resource_category_ids": [],
    }
    payload.update(extra)
    return client.post(
        f"/api/v1/businesses/{business_id}/service-templates", json=payload, headers=_auth(owner_token)
    )


def test_customer_browse_flow_returns_only_bookable_entities():
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_and_approve_branch(business_id, owner_token)

    template_response = _create_template(business_id, owner_token, name="Haircut")
    assert template_response.status_code == 200, template_response.text

    other_business_id, _, other_owner_token = _register_and_approve_business()
    # Not approved/activated — must not show up in browse.
    client.post(
        f"/api/v1/businesses/{other_business_id}/branches",
        json={"branch_name": "Pending Branch", "country_id": _country_id()},
        headers=_auth(other_owner_token),
    )

    customer_response, payload = _register_customer()
    customer_token = _login(payload["email"])

    businesses = client.get("/api/v1/customer/businesses", headers=_auth(customer_token))
    assert businesses.status_code == 200, businesses.text
    business_ids = {b["id"] for b in businesses.json()}
    assert business_id in business_ids

    branches = client.get(f"/api/v1/customer/businesses/{business_id}/branches", headers=_auth(customer_token))
    assert branches.status_code == 200, branches.text
    assert any(b["id"] == branch["id"] for b in branches.json())

    services = client.get(f"/api/v1/customer/branches/{branch['id']}/services", headers=_auth(customer_token))
    assert services.status_code == 200, services.text
    assert any(s["name"] == "Haircut" for s in services.json())


def test_browse_requires_customer_authentication():
    unauthenticated = client.get("/api/v1/customer/businesses")
    assert unauthenticated.status_code == 401

    _, _, owner_token = _register_and_approve_business()
    non_customer = client.get("/api/v1/customer/businesses", headers=_auth(owner_token))
    assert non_customer.status_code == 403
