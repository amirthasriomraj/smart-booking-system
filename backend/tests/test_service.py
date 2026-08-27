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
    owner_username = f"svcowner_{unique}"
    business = _register_business(username=owner_username, email=f"{unique}@example.com")

    admin_username = f"svcadmin_{unique}"
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

    admin_username = f"svcbranchapprover_{unique}"
    _register_business(username=admin_username, email=f"{admin_username}@example.com")
    _promote_to_platform_admin(admin_username)
    admin_token = _login(admin_username)

    approve = client.post(f"/api/v1/branches/{branch['id']}/approve", headers=_auth(admin_token))
    assert approve.status_code == 200, approve.text
    return approve.json()


@pytest.fixture(autouse=True)
def capture_emails(monkeypatch):
    captured = {}

    def fake_invite(email, token, role_code, business_name):
        captured["invite_token"] = token

    def fake_submitted(email, business_name, branch_name, service_name):
        captured["submitted_to"] = email

    def fake_decision(email, business_name, branch_name, service_name, decision, comments=None):
        captured["decision_to"] = email
        captured["decision"] = decision

    monkeypatch.setattr("routers.staff.send_staff_invitation_email", fake_invite)
    monkeypatch.setattr("routers.resources.send_staff_invitation_email", fake_invite)
    monkeypatch.setattr("routers.services.send_service_override_submitted_email", fake_submitted)
    monkeypatch.setattr("routers.services.send_service_override_decision_email", fake_decision)
    return captured


def _invite_and_accept_staff(business_id, owner_token, role_code, branch_id=None):
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


# -----------------------------
# Service Template (ID-018, ID-019, ID-025)
# -----------------------------

def test_owner_can_create_service_template():
    business_id, _, owner_token = _register_and_approve_business()
    response = _create_template(business_id, owner_token, name="Haircut", default_buffer_minutes=10)
    assert response.status_code == 200, response.text
    template = response.json()
    assert template["name"] == "Haircut"
    assert template["business_id"] == business_id
    assert template["status"] == "Active"
    assert template["default_buffer_minutes"] == 10

    db = SessionLocal()
    try:
        audit_entry = db.query(AuditLog).filter(
            AuditLog.entity_type == "ServiceTemplate",
            AuditLog.entity_id == template["id"],
            AuditLog.action == "SERVICE_TEMPLATE_CREATED",
        ).first()
        assert audit_entry is not None
    finally:
        db.close()


def test_non_owner_cannot_create_service_template():
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_and_approve_branch(business_id, owner_token)
    _, bm_token = _invite_and_accept_staff(business_id, owner_token, "BRANCH_MANAGER", branch["id"])

    response = _create_template(business_id, bm_token)
    assert response.status_code == 403


def test_branch_manager_can_read_but_not_write_templates():
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_and_approve_branch(business_id, owner_token)
    _create_template(business_id, owner_token, name="Consult")
    _, bm_token = _invite_and_accept_staff(business_id, owner_token, "BRANCH_MANAGER", branch["id"])

    listing = client.get(f"/api/v1/businesses/{business_id}/service-templates", headers=_auth(bm_token))
    assert listing.status_code == 200
    assert len(listing.json()) >= 1


def test_service_template_has_no_general_update_endpoint():
    """ID-019: create-once + Active/Inactive toggle only."""
    business_id, _, owner_token = _register_and_approve_business()
    template = _create_template(business_id, owner_token).json()

    response = client.patch(
        f"/api/v1/service-templates/{template['id']}", json={"name": "Renamed"}, headers=_auth(owner_token)
    )
    assert response.status_code in (404, 405)


def test_owner_can_toggle_template_status():
    business_id, _, owner_token = _register_and_approve_business()
    template = _create_template(business_id, owner_token).json()

    deactivate = client.post(
        f"/api/v1/service-templates/{template['id']}/deactivate", headers=_auth(owner_token)
    )
    assert deactivate.status_code == 200, deactivate.text
    assert deactivate.json()["status"] == "Inactive"

    activate = client.post(
        f"/api/v1/service-templates/{template['id']}/activate", headers=_auth(owner_token)
    )
    assert activate.status_code == 200, activate.text
    assert activate.json()["status"] == "Active"


def test_template_deactivation_does_not_cascade_to_existing_branch_services():
    """ID-026."""
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_and_approve_branch(business_id, owner_token)
    template = _create_template(business_id, owner_token).json()

    branch_services = client.get(
        f"/api/v1/branches/{branch['id']}/branch-services", headers=_auth(owner_token)
    ).json()
    branch_service = next(bs for bs in branch_services if bs["service_template_id"] == template["id"])
    assert branch_service["status"] == "Approved"

    client.post(f"/api/v1/service-templates/{template['id']}/deactivate", headers=_auth(owner_token))

    refetched = client.get(f"/api/v1/branch-services/{branch_service['id']}", headers=_auth(owner_token)).json()
    assert refetched["status"] == "Approved"


def test_cross_tenant_resource_category_rejected_on_template_creation():
    business_a_id, _, owner_a_token = _register_and_approve_business()
    business_b_id, _, owner_b_token = _register_and_approve_business()
    category_b = _create_category(business_b_id, owner_b_token)

    response = _create_template(
        business_a_id, owner_a_token, default_resource_category_ids=[category_b["id"]]
    )
    assert response.status_code == 400


# -----------------------------
# Service Inheritance (ID-023)
# -----------------------------

def test_new_branch_inherits_existing_active_templates():
    """ID-023(a)."""
    business_id, _, owner_token = _register_and_approve_business()
    template = _create_template(business_id, owner_token, name="Existing Template").json()

    branch = _create_and_approve_branch(business_id, owner_token)

    listing = client.get(f"/api/v1/branches/{branch['id']}/branch-services", headers=_auth(owner_token))
    assert listing.status_code == 200
    matches = [bs for bs in listing.json() if bs["service_template_id"] == template["id"]]
    assert len(matches) == 1
    branch_service = matches[0]
    assert branch_service["status"] == "Approved"
    assert branch_service["pending_approval"] is False
    assert float(branch_service["price"]) == float(template["default_price"])
    assert branch_service["duration"] == template["default_duration"]


def test_new_template_propagates_to_existing_branches():
    """ID-023(b)."""
    business_id, _, owner_token = _register_and_approve_business()
    branch_1 = _create_and_approve_branch(business_id, owner_token)
    branch_2 = _create_and_approve_branch(business_id, owner_token)

    template = _create_template(business_id, owner_token, name="Late Template").json()

    for branch in (branch_1, branch_2):
        listing = client.get(f"/api/v1/branches/{branch['id']}/branch-services", headers=_auth(owner_token)).json()
        matches = [bs for bs in listing if bs["service_template_id"] == template["id"]]
        assert len(matches) == 1
        assert matches[0]["status"] == "Approved"

    db = SessionLocal()
    try:
        created = db.query(AuditLog).filter(
            AuditLog.entity_type == "BranchService",
            AuditLog.action == "BRANCH_SERVICE_CREATED",
        ).count()
        assert created >= 2
    finally:
        db.close()


def test_inactive_template_does_not_propagate_to_new_branch():
    business_id, _, owner_token = _register_and_approve_business()
    template = _create_template(business_id, owner_token, name="Retired").json()
    client.post(f"/api/v1/service-templates/{template['id']}/deactivate", headers=_auth(owner_token))

    branch = _create_and_approve_branch(business_id, owner_token)

    listing = client.get(f"/api/v1/branches/{branch['id']}/branch-services", headers=_auth(owner_token)).json()
    assert all(bs["service_template_id"] != template["id"] for bs in listing)


# -----------------------------
# Branch Service overrides + approval (ID-020, ID-021, ID-022, ID-027)
# -----------------------------

def _setup_business_branch_template_bm():
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_and_approve_branch(business_id, owner_token)
    template = _create_template(business_id, owner_token, name="Haircut").json()
    _, bm_token = _invite_and_accept_staff(business_id, owner_token, "BRANCH_MANAGER", branch["id"])

    branch_services = client.get(
        f"/api/v1/branches/{branch['id']}/branch-services", headers=_auth(owner_token)
    ).json()
    branch_service = next(bs for bs in branch_services if bs["service_template_id"] == template["id"])
    return business_id, owner_token, branch, template, bm_token, branch_service


def test_branch_manager_can_submit_override_for_own_branch():
    business_id, owner_token, branch, template, bm_token, branch_service = _setup_business_branch_template_bm()

    response = client.post(
        f"/api/v1/branch-services/{branch_service['id']}/submit-override",
        json={"price": "350.00", "duration": 45},
        headers=_auth(bm_token),
    )
    assert response.status_code == 200, response.text
    approval = response.json()
    assert approval["decision"] == "Pending"
    assert approval["proposed_configuration"]["price"] == "350.00" or float(approval["proposed_configuration"]["price"]) == 350.00
    assert approval["proposed_configuration"]["duration"] == 45

    # Live values remain the prior approved configuration while pending (§15.4/BR-034).
    refetched = client.get(f"/api/v1/branch-services/{branch_service['id']}", headers=_auth(owner_token)).json()
    assert refetched["status"] == "Approved"
    assert refetched["pending_approval"] is True
    assert float(refetched["price"]) == float(template["default_price"])
    assert refetched["duration"] == template["default_duration"]


def test_branch_manager_cannot_submit_override_for_other_branch():
    business_id, _, owner_token = _register_and_approve_business()
    branch_1 = _create_and_approve_branch(business_id, owner_token)
    branch_2 = _create_and_approve_branch(business_id, owner_token)
    template = _create_template(business_id, owner_token).json()
    _, bm_token = _invite_and_accept_staff(business_id, owner_token, "BRANCH_MANAGER", branch_1["id"])

    other_branch_services = client.get(
        f"/api/v1/branches/{branch_2['id']}/branch-services", headers=_auth(owner_token)
    ).json()
    other_branch_service = next(bs for bs in other_branch_services if bs["service_template_id"] == template["id"])

    response = client.post(
        f"/api/v1/branch-services/{other_branch_service['id']}/submit-override",
        json={"price": "999.00"},
        headers=_auth(bm_token),
    )
    assert response.status_code == 403


def test_hr_and_platform_admin_denied_service_access():
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_and_approve_branch(business_id, owner_token)
    template = _create_template(business_id, owner_token).json()
    _, hr_token = _invite_and_accept_staff(business_id, owner_token, "HR_USER")

    admin_username = f"svcpa_{uuid.uuid4().hex[:8]}"
    _register_business(username=admin_username, email=f"{admin_username}@example.com")
    _promote_to_platform_admin(admin_username)
    admin_token = _login(admin_username)

    for token in (hr_token, admin_token):
        response = client.get(f"/api/v1/businesses/{business_id}/service-templates", headers=_auth(token))
        assert response.status_code == 403

        response = client.get(f"/api/v1/branches/{branch['id']}/branch-services", headers=_auth(token))
        assert response.status_code == 403


def test_second_submission_blocked_while_one_pending():
    business_id, owner_token, branch, template, bm_token, branch_service = _setup_business_branch_template_bm()

    first = client.post(
        f"/api/v1/branch-services/{branch_service['id']}/submit-override",
        json={"price": "350.00"},
        headers=_auth(bm_token),
    )
    assert first.status_code == 200

    second = client.post(
        f"/api/v1/branch-services/{branch_service['id']}/submit-override",
        json={"price": "400.00"},
        headers=_auth(bm_token),
    )
    assert second.status_code == 409


def test_approval_applies_proposed_values_and_retains_history():
    business_id, owner_token, branch, template, bm_token, branch_service = _setup_business_branch_template_bm()

    submit = client.post(
        f"/api/v1/branch-services/{branch_service['id']}/submit-override",
        json={"price": "350.00", "duration": 45},
        headers=_auth(bm_token),
    )
    approval_id = submit.json()["id"]

    decide = client.post(
        f"/api/v1/service-approvals/{approval_id}/decide",
        json={"decision": "Approved", "comments": "Looks good"},
        headers=_auth(owner_token),
    )
    assert decide.status_code == 200, decide.text
    assert decide.json()["decision"] == "Approved"

    refetched = client.get(f"/api/v1/branch-services/{branch_service['id']}", headers=_auth(owner_token)).json()
    assert refetched["status"] == "Approved"
    assert refetched["pending_approval"] is False
    assert float(refetched["price"]) == 350.00
    assert refetched["duration"] == 45

    db = SessionLocal()
    try:
        from models import ServiceApproval
        record = db.query(ServiceApproval).filter(ServiceApproval.id == approval_id).first()
        assert record is not None
        assert record.decision == "Approved"
        assert record.previous_configuration is not None
        assert record.proposed_configuration is not None

        audit_entry = db.query(AuditLog).filter(
            AuditLog.entity_type == "ServiceApproval",
            AuditLog.entity_id == approval_id,
            AuditLog.action == "SERVICE_OVERRIDE_APPROVED",
        ).first()
        assert audit_entry is not None
    finally:
        db.close()


def test_rejection_leaves_live_values_unchanged_and_retains_history():
    business_id, owner_token, branch, template, bm_token, branch_service = _setup_business_branch_template_bm()

    submit = client.post(
        f"/api/v1/branch-services/{branch_service['id']}/submit-override",
        json={"price": "350.00"},
        headers=_auth(bm_token),
    )
    approval_id = submit.json()["id"]

    decide = client.post(
        f"/api/v1/service-approvals/{approval_id}/decide",
        json={"decision": "Rejected", "comments": "Not approved"},
        headers=_auth(owner_token),
    )
    assert decide.status_code == 200, decide.text

    refetched = client.get(f"/api/v1/branch-services/{branch_service['id']}", headers=_auth(owner_token)).json()
    assert refetched["pending_approval"] is False
    assert float(refetched["price"]) == float(template["default_price"])

    db = SessionLocal()
    try:
        audit_entry = db.query(AuditLog).filter(
            AuditLog.entity_type == "ServiceApproval",
            AuditLog.entity_id == approval_id,
            AuditLog.action == "SERVICE_OVERRIDE_REJECTED",
        ).first()
        assert audit_entry is not None
    finally:
        db.close()


def test_owner_direct_update_only_accepts_customization_fields():
    business_id, owner_token, branch, template, bm_token, branch_service = _setup_business_branch_template_bm()

    response = client.patch(
        f"/api/v1/branch-services/{branch_service['id']}",
        json={"price": "500.00", "duration": 60},
        headers=_auth(owner_token),
    )
    assert response.status_code == 200, response.text
    updated = response.json()
    assert float(updated["price"]) == 500.00
    assert updated["duration"] == 60
    assert updated["status"] == "Approved"
    assert updated["pending_approval"] is False


def test_owner_direct_update_rejects_system_lifecycle_fields():
    business_id, owner_token, branch, template, bm_token, branch_service = _setup_business_branch_template_bm()

    for forbidden_field, value in (
        ("status", "Suspended"),
        ("pending_approval", True),
        ("service_template_id", template["id"]),
        ("branch_id", branch["id"]),
        ("business_id", business_id),
    ):
        response = client.patch(
            f"/api/v1/branch-services/{branch_service['id']}",
            json={forbidden_field: value},
            headers=_auth(owner_token),
        )
        assert response.status_code == 422, f"{forbidden_field} should be rejected, got {response.status_code}"


def test_cross_tenant_resource_category_rejected_on_override():
    business_id, owner_token, branch, template, bm_token, branch_service = _setup_business_branch_template_bm()
    other_business_id, _, other_owner_token = _register_and_approve_business()
    other_category = _create_category(other_business_id, other_owner_token)

    response = client.post(
        f"/api/v1/branch-services/{branch_service['id']}/submit-override",
        json={"resource_category_ids": [other_category["id"]]},
        headers=_auth(bm_token),
    )
    assert response.status_code == 400


def test_notifications_sent_on_submit_and_decision(capture_emails):
    business_id, owner_token, branch, template, bm_token, branch_service = _setup_business_branch_template_bm()

    submit = client.post(
        f"/api/v1/branch-services/{branch_service['id']}/submit-override",
        json={"price": "350.00"},
        headers=_auth(bm_token),
    )
    approval_id = submit.json()["id"]
    assert capture_emails.get("submitted_to")

    client.post(
        f"/api/v1/service-approvals/{approval_id}/decide",
        json={"decision": "Approved"},
        headers=_auth(owner_token),
    )
    assert capture_emails.get("decision") == "Approved"
