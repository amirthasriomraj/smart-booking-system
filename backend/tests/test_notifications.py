import uuid

import pytest
from fastapi.testclient import TestClient

from main import app
from database import SessionLocal
from models import Role, BusinessCategory, Country, Business, Branch, User, Notification

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


def _admin_token():
    unique = uuid.uuid4().hex[:8]
    admin_username = f"notifadmin_{unique}"
    _register_business(username=admin_username, email=f"{admin_username}@example.com")
    _promote_to_platform_admin(admin_username)
    return _login(admin_username)


def _notification(business_id, recipient_user_id, notification_type):
    db = SessionLocal()
    try:
        query = db.query(Notification).filter(
            Notification.recipient_user_id == recipient_user_id,
            Notification.notification_type == notification_type,
        )
        if business_id is not None:
            query = query.filter(Notification.business_id == business_id)
        return query.order_by(Notification.id.desc()).first()
    finally:
        db.close()


def _owner_user_id(business_id):
    db = SessionLocal()
    try:
        business = db.query(Business).filter(Business.id == business_id).first()
        return business.owner_user_id
    finally:
        db.close()


# -----------------------------
# Welcome Email — Business registration
# -----------------------------

def test_welcome_notification_persisted_on_business_registration():
    response = _register_business()
    assert response.status_code == 200
    business_id = response.json()["id"]
    owner_user_id = _owner_user_id(business_id)

    notification = _notification(business_id, owner_user_id, "Welcome")
    assert notification is not None
    assert notification.status == "Sent"
    assert notification.channel == "Email"


# -----------------------------
# Welcome Email — Customer self-registration
# -----------------------------

def test_welcome_notification_persisted_on_customer_registration():
    unique = uuid.uuid4().hex[:8]
    payload = {
        "first_name": "Test",
        "last_name": "Customer",
        "email": f"cust_{unique}@example.com",
        "mobile_number": "9999999999",
        "password": "Testpass123!",
    }
    response = client.post("/api/v1/customers/register", json=payload)
    assert response.status_code == 200, response.text
    user_id = response.json()["user_id"]

    notification = _notification(None, user_id, "Welcome")
    assert notification is not None
    assert notification.status == "Sent"


# -----------------------------
# Business Approved / Rejected
# -----------------------------

def test_business_approved_notification_persisted():
    admin_token = _admin_token()
    target = _register_business()
    business_id = target.json()["id"]
    owner_user_id = _owner_user_id(business_id)

    response = client.post(
        f"/api/v1/businesses/{business_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200

    notification = _notification(business_id, owner_user_id, "BusinessApproved")
    assert notification is not None
    assert notification.status == "Sent"
    assert notification.related_entity_type == "Business"
    assert notification.related_entity_id == business_id


def test_business_rejected_notification_persisted():
    admin_token = _admin_token()
    target = _register_business()
    business_id = target.json()["id"]
    owner_user_id = _owner_user_id(business_id)

    response = client.post(
        f"/api/v1/businesses/{business_id}/reject",
        json={"reason": "Incomplete documentation"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200

    notification = _notification(business_id, owner_user_id, "BusinessRejected")
    assert notification is not None
    assert notification.status == "Sent"


# -----------------------------
# Branch Approved / Rejected
# -----------------------------

def _create_and_activate_business(owner_username):
    admin_token = _admin_token()
    reg = _register_business(username=owner_username, email=f"{owner_username}@example.com")
    business_id = reg.json()["id"]
    client.post(
        f"/api/v1/businesses/{business_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    return business_id, admin_token


def test_branch_approved_notification_persisted():
    unique = uuid.uuid4().hex[:8]
    owner_username = f"branchowner_{unique}"
    business_id, admin_token = _create_and_activate_business(owner_username)
    owner_token = _login(owner_username)
    owner_user_id = _owner_user_id(business_id)

    branch_response = client.post(
        f"/api/v1/businesses/{business_id}/branches",
        json={"branch_name": f"Branch {unique}", "country_id": _country_id()},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert branch_response.status_code == 200, branch_response.text
    branch_id = branch_response.json()["id"]

    response = client.post(
        f"/api/v1/branches/{branch_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text

    notification = _notification(business_id, owner_user_id, "BranchApproved")
    assert notification is not None
    assert notification.status == "Sent"
    assert notification.related_entity_type == "Branch"
    assert notification.related_entity_id == branch_id


def test_branch_rejected_notification_persisted():
    unique = uuid.uuid4().hex[:8]
    owner_username = f"branchowner2_{unique}"
    business_id, admin_token = _create_and_activate_business(owner_username)
    owner_token = _login(owner_username)
    owner_user_id = _owner_user_id(business_id)

    branch_response = client.post(
        f"/api/v1/businesses/{business_id}/branches",
        json={"branch_name": f"Branch {unique}", "country_id": _country_id()},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    branch_id = branch_response.json()["id"]

    response = client.post(
        f"/api/v1/branches/{branch_id}/reject",
        json={"reason": "Address could not be verified"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text

    notification = _notification(business_id, owner_user_id, "BranchRejected")
    assert notification is not None
    assert notification.status == "Sent"


# -----------------------------
# Invitation Accepted
# -----------------------------

def test_invitation_accepted_notification_persisted(monkeypatch):
    captured = {}

    def fake_invite(email, token, role_code, business_name):
        captured["token"] = token

    monkeypatch.setattr("routers.staff.send_staff_invitation_email", fake_invite)

    unique = uuid.uuid4().hex[:8]
    owner_username = f"inviteowner2_{unique}"
    business_id, admin_token = _create_and_activate_business(owner_username)
    owner_token = _login(owner_username)
    owner_user_id = _owner_user_id(business_id)

    invite_response = client.post(
        f"/api/v1/businesses/{business_id}/staff/invite",
        json={
            "email": f"invitee2_{unique}@example.com",
            "role_code": "HR_USER",
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert invite_response.status_code == 200, invite_response.text
    assert "token" in captured

    accept_response = client.post(
        "/api/v1/auth/accept-invitation",
        json={
            "token": captured["token"],
            "username": f"newhr_{unique}",
            "password": "Testpass123!",
        },
    )
    assert accept_response.status_code == 200, accept_response.text

    notification = _notification(business_id, owner_user_id, "InvitationAccepted")
    assert notification is not None
    assert notification.status == "Sent"
