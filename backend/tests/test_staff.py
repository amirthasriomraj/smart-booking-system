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
    BusinessMember,
    BranchAssignment,
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
    """Returns (business_id, owner_username, owner_token) for an Active business."""
    unique = uuid.uuid4().hex[:8]
    owner_username = f"activeowner_{unique}"
    business = _register_business(username=owner_username, email=f"{unique}@example.com")

    admin_username = f"staffadmin_{unique}"
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

    admin_username = f"branchapprover_{unique}"
    _register_business(username=admin_username, email=f"{admin_username}@example.com")
    _promote_to_platform_admin(admin_username)
    admin_token = _login(admin_username)

    approve = client.post(f"/api/v1/branches/{branch['id']}/approve", headers=_auth(admin_token))
    assert approve.status_code == 200, approve.text
    return approve.json()


def _invite(business_id, owner_token, email, role_code, branch_id=None):
    payload = {"email": email, "role_code": role_code}
    if branch_id is not None:
        payload["branch_id"] = branch_id
    return client.post(
        f"/api/v1/businesses/{business_id}/staff/invite",
        json=payload,
        headers=_auth(owner_token),
    )


# -----------------------------
# Capture the emailed token instead of actually sending SMTP
# -----------------------------

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


def _register_plain_user(username=None, email=None, password="Testpass123"):
    unique = uuid.uuid4().hex[:8]
    payload = {
        "username": username or f"user_{unique}",
        "email": email or f"{unique}@example.com",
        "password": password,
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


# -----------------------------
# Invite — Case A (brand-new email)
# -----------------------------

def test_invite_branch_manager_case_a_creates_pending_member_without_branch_assignment(capture_invitation_email):
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_and_approve_branch(business_id, owner_token)

    unique = uuid.uuid4().hex[:8]
    email = f"newbm_{unique}@example.com"
    response = _invite(business_id, owner_token, email, "BRANCH_MANAGER", branch["id"])
    assert response.status_code == 200, response.text
    member = response.json()

    assert member["status"] == "Pending"
    assert member["role_code"] == "BRANCH_MANAGER"
    assert member["email"] == email
    assert member["current_branch_id"] is None  # ID-010: no BranchAssignment yet

    db = SessionLocal()
    try:
        row = db.query(BusinessMember).filter(BusinessMember.id == member["id"]).first()
        assert row.requires_credential_setup is True
        assert row.invited_branch_id == branch["id"]
        assert (
            db.query(BranchAssignment)
            .filter(BranchAssignment.business_member_id == row.id)
            .first()
            is None
        )

        placeholder_user = db.query(User).filter(User.id == row.user_id).first()
        assert placeholder_user.is_active is False

        profiles = db.query(UserProfile).filter(UserProfile.user_id == placeholder_user.id).all()
        assert len(profiles) == 1  # every User gets exactly one UserProfile, same as create_user/register_business

        audit_entry = db.query(AuditLog).filter(
            AuditLog.entity_type == "BusinessMember",
            AuditLog.entity_id == member["id"],
            AuditLog.action == "EMPLOYEE_INVITED",
        ).first()
        assert audit_entry is not None
    finally:
        db.close()

    assert capture_invitation_email["email"] == email
    assert capture_invitation_email["role_code"] == "BRANCH_MANAGER"


def test_invite_hr_user_case_a_has_no_branch_assignment_ever(capture_invitation_email):
    business_id, _, owner_token = _register_and_approve_business()

    unique = uuid.uuid4().hex[:8]
    email = f"newhr_{unique}@example.com"
    response = _invite(business_id, owner_token, email, "HR_USER")
    assert response.status_code == 200, response.text
    member = response.json()
    assert member["role_code"] == "HR_USER"

    db = SessionLocal()
    try:
        row = db.query(BusinessMember).filter(BusinessMember.id == member["id"]).first()
        assert row.invited_branch_id is None
    finally:
        db.close()

    status_response = client.get(
        "/api/v1/auth/accept-invitation", params={"token": capture_invitation_email["token"]}
    )
    assert status_response.status_code == 200, status_response.text
    status_body = status_response.json()
    assert status_body["branch_id"] is None
    assert status_body["branch_name"] is None


def test_invite_branch_manager_requires_approved_branch():
    business_id, _, owner_token = _register_and_approve_business()

    unique = uuid.uuid4().hex[:8]
    pending_branch = client.post(
        f"/api/v1/businesses/{business_id}/branches",
        json={"branch_name": f"Pending {unique}", "country_id": _country_id()},
        headers=_auth(owner_token),
    ).json()

    response = _invite(business_id, owner_token, f"bm_{unique}@example.com", "BRANCH_MANAGER", pending_branch["id"])
    assert response.status_code == 409


def test_invite_rejected_for_non_owner_and_other_business():
    business_id, _, owner_token = _register_and_approve_business()
    other_business_id, _, other_owner_token = _register_and_approve_business()

    unique = uuid.uuid4().hex[:8]
    response = _invite(business_id, other_owner_token, f"x_{unique}@example.com", "HR_USER")
    assert response.status_code == 403


# -----------------------------
# Accept invitation — Case A
# -----------------------------

def test_accept_invitation_case_a_activates_user_and_creates_branch_assignment(capture_invitation_email):
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_and_approve_branch(business_id, owner_token)

    unique = uuid.uuid4().hex[:8]
    email = f"acceptbm_{unique}@example.com"
    invite_response = _invite(business_id, owner_token, email, "BRANCH_MANAGER", branch["id"])
    member_id = invite_response.json()["id"]
    token = capture_invitation_email["token"]

    status_response = client.get("/api/v1/auth/accept-invitation", params={"token": token})
    assert status_response.status_code == 200, status_response.text
    status_body = status_response.json()
    assert status_body["requires_credential_setup"] is True
    assert status_body["branch_id"] == branch["id"]
    assert status_body["branch_name"] == branch["branch_name"]

    accept_response = client.post(
        "/api/v1/auth/accept-invitation",
        json={"token": token, "username": f"bmuser_{unique}", "password": "Testpass123"},
    )
    assert accept_response.status_code == 200, accept_response.text

    db = SessionLocal()
    try:
        member = db.query(BusinessMember).filter(BusinessMember.id == member_id).first()
        assert member.status == "Active"
        assert member.invitation_token_hash is None
        assert member.invited_branch_id is None

        assignment = (
            db.query(BranchAssignment)
            .filter(BranchAssignment.business_member_id == member.id, BranchAssignment.is_current == True)  # noqa: E712
            .first()
        )
        assert assignment is not None
        assert assignment.branch_id == branch["id"]

        user = db.query(User).filter(User.id == member.user_id).first()
        assert user.is_active is True
        assert user.username == f"bmuser_{unique}"

        audit_entry = db.query(AuditLog).filter(
            AuditLog.entity_type == "BusinessMember",
            AuditLog.entity_id == member.id,
            AuditLog.action == "INVITATION_ACCEPTED",
        ).first()
        assert audit_entry is not None
    finally:
        db.close()

    # New Branch Manager can log in and /auth/me reflects the branch.
    bm_token = _login(f"bmuser_{unique}")
    me_response = client.get("/api/v1/auth/me", headers=_auth(bm_token))
    assert me_response.status_code == 200
    me = me_response.json()
    assert me["business"]["role_code"] == "BRANCH_MANAGER"
    assert me["business"]["branch_id"] == branch["id"]


def test_accept_invitation_case_a_missing_credentials_rejected(capture_invitation_email):
    business_id, _, owner_token = _register_and_approve_business()
    unique = uuid.uuid4().hex[:8]
    _invite(business_id, owner_token, f"nocreds_{unique}@example.com", "HR_USER")
    token = capture_invitation_email["token"]

    response = client.post("/api/v1/auth/accept-invitation", json={"token": token})
    assert response.status_code == 400


def test_expired_or_invalid_token_rejected():
    response = client.post("/api/v1/auth/accept-invitation", json={"token": "not-a-real-token"})
    assert response.status_code == 400

    status_response = client.get("/api/v1/auth/accept-invitation", params={"token": "not-a-real-token"})
    assert status_response.status_code == 400


# -----------------------------
# Invite / Accept — Case B (existing user reused)
# -----------------------------

def test_invite_existing_user_case_b_reuses_user_without_modifying_credentials(capture_invitation_email):
    business_id, _, owner_token = _register_and_approve_business()

    unique = uuid.uuid4().hex[:8]
    existing_email = f"existing_{unique}@example.com"
    existing_username = f"existinguser_{unique}"
    _register_plain_user(username=existing_username, email=existing_email, password="OriginalPass1")

    invite_response = _invite(business_id, owner_token, existing_email, "HR_USER")
    assert invite_response.status_code == 200, invite_response.text
    member = invite_response.json()

    db = SessionLocal()
    try:
        row = db.query(BusinessMember).filter(BusinessMember.id == member["id"]).first()
        assert row.requires_credential_setup is False
        user = db.query(User).filter(User.id == row.user_id).first()
        assert user.username == existing_username

        # Case B reuses the existing User (and its existing UserProfile from
        # registration) — no duplicate/new UserProfile is created by invite.
        profiles = db.query(UserProfile).filter(UserProfile.user_id == user.id).all()
        assert len(profiles) == 1
    finally:
        db.close()

    status_response = client.get("/api/v1/auth/accept-invitation", params={"token": capture_invitation_email["token"]})
    assert status_response.status_code == 200
    assert status_response.json()["requires_credential_setup"] is False

    # Supplying credentials for a case-B token is rejected.
    bad_accept = client.post(
        "/api/v1/auth/accept-invitation",
        json={"token": capture_invitation_email["token"], "username": "sneaky", "password": "Whatever123"},
    )
    assert bad_accept.status_code == 400

    accept_response = client.post(
        "/api/v1/auth/accept-invitation",
        json={"token": capture_invitation_email["token"]},
    )
    assert accept_response.status_code == 200, accept_response.text

    db = SessionLocal()
    try:
        row = db.query(BusinessMember).filter(BusinessMember.id == member["id"]).first()
        assert row.status == "Active"
        user = db.query(User).filter(User.id == row.user_id).first()
        assert user.username == existing_username  # untouched
    finally:
        db.close()

    # Original credentials still work.
    original_token = _login(existing_username, password="OriginalPass1")
    assert original_token


# -----------------------------
# Duplicate / same-business rehire
# -----------------------------

def test_duplicate_invite_blocked_when_active_or_pending_membership_exists():
    business_id, _, owner_token = _register_and_approve_business()
    other_business_id, _, other_owner_token = _register_and_approve_business()

    unique = uuid.uuid4().hex[:8]
    email = f"dup_{unique}@example.com"
    first = _invite(business_id, owner_token, email, "HR_USER")
    assert first.status_code == 200

    second = _invite(other_business_id, other_owner_token, email, "HR_USER")
    assert second.status_code == 409


def test_same_business_rehire_after_deactivation_rejected_explicitly(capture_invitation_email):
    business_id, _, owner_token = _register_and_approve_business()
    unique = uuid.uuid4().hex[:8]
    email = f"rehire_{unique}@example.com"

    invite = _invite(business_id, owner_token, email, "HR_USER")
    member_id = invite.json()["id"]
    client.post("/api/v1/auth/accept-invitation", json={"token": capture_invitation_email["token"], "username": f"rehireuser_{unique}", "password": "Testpass123"})

    deactivate = client.post(f"/api/v1/business-members/{member_id}/deactivate", headers=_auth(owner_token))
    assert deactivate.status_code == 200, deactivate.text

    reinvite = _invite(business_id, owner_token, email, "HR_USER")
    assert reinvite.status_code == 409


# -----------------------------
# BR-022 end-to-end
# -----------------------------

def test_br022_cross_business_movement_after_deactivation(capture_invitation_email):
    business_a_id, _, owner_a_token = _register_and_approve_business()
    branch_a = _create_and_approve_branch(business_a_id, owner_a_token)

    unique = uuid.uuid4().hex[:8]
    email = f"br022_{unique}@example.com"
    username = f"br022user_{unique}"

    invite_a = _invite(business_a_id, owner_a_token, email, "BRANCH_MANAGER", branch_a["id"])
    member_a_id = invite_a.json()["id"]
    accept_a = client.post(
        "/api/v1/auth/accept-invitation",
        json={"token": capture_invitation_email["token"], "username": username, "password": "Testpass123"},
    )
    assert accept_a.status_code == 200, accept_a.text

    deactivate = client.post(f"/api/v1/business-members/{member_a_id}/deactivate", headers=_auth(owner_a_token))
    assert deactivate.status_code == 200, deactivate.text

    db = SessionLocal()
    try:
        member_a = db.query(BusinessMember).filter(BusinessMember.id == member_a_id).first()
        assert member_a.status == "Inactive"
        assignment_a = db.query(BranchAssignment).filter(BranchAssignment.business_member_id == member_a_id).first()
        assert assignment_a.is_current is False
        assert assignment_a.assigned_to is not None
    finally:
        db.close()

    business_b_id, _, owner_b_token = _register_and_approve_business()
    invite_b = _invite(business_b_id, owner_b_token, email, "HR_USER")
    assert invite_b.status_code == 200, invite_b.text  # Inactive elsewhere does not block

    accept_b = client.post(
        "/api/v1/auth/accept-invitation",
        json={"token": capture_invitation_email["token"]},  # case B: no credential fields
    )
    assert accept_b.status_code == 200, accept_b.text

    # Original credentials from Business A still work, now resolving to Business B.
    token = _login(username, password="Testpass123")
    me = client.get("/api/v1/auth/me", headers=_auth(token)).json()
    assert me["business"]["id"] == business_b_id
    assert me["business"]["role_code"] == "HR_USER"

    # Business A's history is untouched.
    db = SessionLocal()
    try:
        member_a = db.query(BusinessMember).filter(BusinessMember.id == member_a_id).first()
        assert member_a.status == "Inactive"
    finally:
        db.close()


# -----------------------------
# is_active is not the discriminator
# -----------------------------

def test_administratively_deactivated_user_is_still_treated_as_case_b(capture_invitation_email):
    business_id, _, owner_token = _register_and_approve_business()

    unique = uuid.uuid4().hex[:8]
    email = f"adminlocked_{unique}@example.com"
    username = f"adminlocked_{unique}"
    _register_plain_user(username=username, email=email, password="Testpass123")

    # Legacy admin path unrelated to invitations.
    admin_username = f"legacyadmin_{unique}"
    _register_business(username=admin_username, email=f"{admin_username}@example.com")
    db = SessionLocal()
    try:
        admin_user = db.query(User).filter(User.username == admin_username).first()
        admin_user.role = "admin"
        db.commit()
    finally:
        db.close()
    admin_token = _login(admin_username)

    lock = client.patch(f"/api/v1/users/deactivate/{_user_id(username)}", headers=_auth(admin_token))
    assert lock.status_code == 200, lock.text

    invite = _invite(business_id, owner_token, email, "HR_USER")
    assert invite.status_code == 200, invite.text
    member = invite.json()

    db = SessionLocal()
    try:
        row = db.query(BusinessMember).filter(BusinessMember.id == member["id"]).first()
        assert row.requires_credential_setup is False  # correctly case B, not inferred from is_active
    finally:
        db.close()

    accept = client.post("/api/v1/auth/accept-invitation", json={"token": capture_invitation_email["token"]})
    assert accept.status_code == 200, accept.text

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        assert user.is_active is False  # untouched by acceptance
    finally:
        db.close()


def _user_id(username):
    db = SessionLocal()
    try:
        return db.query(User).filter(User.username == username).first().id
    finally:
        db.close()


# -----------------------------
# Resend
# -----------------------------

def test_resend_regenerates_token_and_invalidates_old_one(capture_invitation_email):
    business_id, _, owner_token = _register_and_approve_business()
    unique = uuid.uuid4().hex[:8]
    email = f"resend_{unique}@example.com"

    invite = _invite(business_id, owner_token, email, "HR_USER")
    member_id = invite.json()["id"]
    old_token = capture_invitation_email["token"]

    resend = client.post(
        f"/api/v1/businesses/{business_id}/staff/{member_id}/resend-invite",
        headers=_auth(owner_token),
    )
    assert resend.status_code == 200, resend.text
    new_token = capture_invitation_email["token"]
    assert new_token != old_token

    old_attempt = client.get("/api/v1/auth/accept-invitation", params={"token": old_token})
    assert old_attempt.status_code == 400

    new_attempt = client.get("/api/v1/auth/accept-invitation", params={"token": new_token})
    assert new_attempt.status_code == 200

    db = SessionLocal()
    try:
        audit_entry = db.query(AuditLog).filter(
            AuditLog.entity_type == "BusinessMember",
            AuditLog.entity_id == member_id,
            AuditLog.action == "INVITATION_RESENT",
        ).first()
        assert audit_entry is not None
    finally:
        db.close()


def test_resend_only_works_while_pending(capture_invitation_email):
    business_id, _, owner_token = _register_and_approve_business()
    unique = uuid.uuid4().hex[:8]
    email = f"resendactive_{unique}@example.com"

    invite = _invite(business_id, owner_token, email, "HR_USER")
    member_id = invite.json()["id"]
    client.post(
        "/api/v1/auth/accept-invitation",
        json={"token": capture_invitation_email["token"], "username": f"resendactive_{unique}", "password": "Testpass123"},
    )

    resend = client.post(
        f"/api/v1/businesses/{business_id}/staff/{member_id}/resend-invite",
        headers=_auth(owner_token),
    )
    assert resend.status_code == 409


# -----------------------------
# Transfer
# -----------------------------

def test_transfer_moves_active_branch_manager_preserving_history(capture_invitation_email):
    business_id, _, owner_token = _register_and_approve_business()
    branch_1 = _create_and_approve_branch(business_id, owner_token, "Branch One")
    branch_2 = _create_and_approve_branch(business_id, owner_token, "Branch Two")

    unique = uuid.uuid4().hex[:8]
    email = f"transfer_{unique}@example.com"
    invite = _invite(business_id, owner_token, email, "BRANCH_MANAGER", branch_1["id"])
    member_id = invite.json()["id"]
    client.post(
        "/api/v1/auth/accept-invitation",
        json={"token": capture_invitation_email["token"], "username": f"transferuser_{unique}", "password": "Testpass123"},
    )

    transfer = client.post(
        f"/api/v1/business-members/{member_id}/transfer-branch",
        json={"branch_id": branch_2["id"]},
        headers=_auth(owner_token),
    )
    assert transfer.status_code == 200, transfer.text
    assert transfer.json()["current_branch_id"] == branch_2["id"]

    db = SessionLocal()
    try:
        assignments = (
            db.query(BranchAssignment)
            .filter(BranchAssignment.business_member_id == member_id)
            .order_by(BranchAssignment.assigned_from)
            .all()
        )
        assert len(assignments) == 2
        assert assignments[0].branch_id == branch_1["id"]
        assert assignments[0].is_current is False
        assert assignments[0].assigned_to is not None
        assert assignments[1].branch_id == branch_2["id"]
        assert assignments[1].is_current is True

        audit_entry = db.query(AuditLog).filter(
            AuditLog.entity_type == "BranchAssignment",
            AuditLog.entity_id == member_id,
            AuditLog.action == "EMPLOYEE_TRANSFER",
        ).first()
        assert audit_entry is not None
    finally:
        db.close()


def test_transfer_rejected_for_pending_member_and_for_hr(capture_invitation_email):
    business_id, _, owner_token = _register_and_approve_business()
    branch_1 = _create_and_approve_branch(business_id, owner_token, "Branch One")
    branch_2 = _create_and_approve_branch(business_id, owner_token, "Branch Two")

    unique = uuid.uuid4().hex[:8]

    # Pending Branch Manager — no BranchAssignment exists yet.
    pending_invite = _invite(business_id, owner_token, f"pendingbm_{unique}@example.com", "BRANCH_MANAGER", branch_1["id"])
    pending_id = pending_invite.json()["id"]
    pending_transfer = client.post(
        f"/api/v1/business-members/{pending_id}/transfer-branch",
        json={"branch_id": branch_2["id"]},
        headers=_auth(owner_token),
    )
    assert pending_transfer.status_code == 409

    # Active HR — no BranchAssignment concept at all.
    hr_invite = _invite(business_id, owner_token, f"hr_{unique}@example.com", "HR_USER")
    hr_id = hr_invite.json()["id"]
    client.post(
        "/api/v1/auth/accept-invitation",
        json={"token": capture_invitation_email["token"], "username": f"hruser_{unique}", "password": "Testpass123"},
    )
    hr_transfer = client.post(
        f"/api/v1/business-members/{hr_id}/transfer-branch",
        json={"branch_id": branch_2["id"]},
        headers=_auth(owner_token),
    )
    assert hr_transfer.status_code == 409


# -----------------------------
# Deactivate
# -----------------------------

def test_deactivate_pending_branch_manager_has_nothing_to_close():
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_and_approve_branch(business_id, owner_token)

    unique = uuid.uuid4().hex[:8]
    invite = _invite(business_id, owner_token, f"pendingdeact_{unique}@example.com", "BRANCH_MANAGER", branch["id"])
    member_id = invite.json()["id"]

    deactivate = client.post(f"/api/v1/business-members/{member_id}/deactivate", headers=_auth(owner_token))
    assert deactivate.status_code == 200, deactivate.text

    db = SessionLocal()
    try:
        member = db.query(BusinessMember).filter(BusinessMember.id == member_id).first()
        assert member.status == "Inactive"
        assert member.left_at is not None
        assert db.query(BranchAssignment).filter(BranchAssignment.business_member_id == member_id).first() is None

        audit_entry = db.query(AuditLog).filter(
            AuditLog.entity_type == "BusinessMember",
            AuditLog.entity_id == member_id,
            AuditLog.action == "EMPLOYEE_DEACTIVATED",
        ).first()
        assert audit_entry is not None
    finally:
        db.close()
