"""M9 Phase 6b — new backend endpoints: Platform Admin Audit Logs/
Notifications/Analytics, Business Owner Reports, Branch Manager Daily
Reports, and the Resource User self-scoped bookings endpoint."""

import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from main import app
from database import SessionLocal
from models import Role, BusinessCategory, Country, User, UserRole

client = TestClient(app)

BOOKING_DATE = date.today() + timedelta(days=(7 - date.today().weekday()) % 7 or 7)  # next Monday


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
        "password": "Testpass123!",
        "business_name": business_name or f"Business {unique}",
        "business_category_id": _category_id(),
        "country_id": _country_id(),
    }
    return client.post("/api/v1/businesses/register", json=payload)


def _login(username, password="Testpass123!"):
    response = client.post("/api/v1/auth/login", data={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _promote_to_platform_admin(username):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        role = db.query(Role).filter(Role.code == "PLATFORM_ADMIN").first()
        db.add(UserRole(user_id=user.id, role_id=role.id))
        db.commit()
    finally:
        db.close()


def _register_and_approve_business():
    unique = uuid.uuid4().hex[:8]
    admin_username = f"reportadmin_{unique}"
    _register_business(username=admin_username, email=f"{admin_username}@example.com")
    _promote_to_platform_admin(admin_username)
    admin_token = _login(admin_username)

    owner_username = f"reportowner_{unique}"
    reg = _register_business(username=owner_username, email=f"{owner_username}@example.com")
    business_id = reg.json()["id"]
    owner_token = _login(owner_username)

    approve = client.post(f"/api/v1/businesses/{business_id}/approve", headers=_auth(admin_token))
    assert approve.status_code == 200
    return business_id, owner_token, admin_token


def _create_branch(business_id, owner_token, admin_token, branch_name=None):
    payload = {"branch_name": branch_name or f"Branch {uuid.uuid4().hex[:8]}", "country_id": _country_id()}
    response = client.post(f"/api/v1/businesses/{business_id}/branches", json=payload, headers=_auth(owner_token))
    assert response.status_code == 200, response.text
    branch = response.json()
    approve = client.post(f"/api/v1/branches/{branch['id']}/approve", headers=_auth(admin_token))
    assert approve.status_code == 200
    activate = client.post(f"/api/v1/branches/{branch['id']}/activate", headers=_auth(owner_token))
    assert activate.status_code == 200
    return branch


def _bookable_setup():
    """business (Active) -> branch (Approved+Active) -> Active resource with
    working hours -> Service Template inherited as an Approved BranchService
    -> a walk-in customer."""
    business_id, owner_token, admin_token = _register_and_approve_business()
    branch = _create_branch(business_id, owner_token, admin_token)
    unique = uuid.uuid4().hex[:8]

    category = client.post(
        f"/api/v1/businesses/{business_id}/resource-categories",
        json={"category_name": f"Category {unique}"},
        headers=_auth(owner_token),
    ).json()
    resource = client.post(
        f"/api/v1/branches/{branch['id']}/resources",
        json={"resource_category_id": category["id"], "resource_name": f"Resource {unique}", "requires_login": False},
        headers=_auth(owner_token),
    ).json()
    activate = client.post(f"/api/v1/resources/{resource['id']}/activate", headers=_auth(owner_token))
    assert activate.status_code == 200, activate.text
    hours = client.put(
        f"/api/v1/resources/{resource['id']}/working-hours",
        json={"hours": [{"weekday": BOOKING_DATE.weekday(), "opening_time": "09:00:00", "closing_time": "17:00:00"}]},
        headers=_auth(owner_token),
    )
    assert hours.status_code == 200, hours.text

    template = client.post(
        f"/api/v1/businesses/{business_id}/service-templates",
        json={
            "name": f"Template {unique}", "default_duration": 30, "default_price": "100.00",
            "default_resource_category_ids": [category["id"]],
        },
        headers=_auth(owner_token),
    ).json()
    branch_services = client.get(
        f"/api/v1/businesses/{business_id}/branch-services", headers=_auth(owner_token)
    ).json()["items"]
    branch_service = next(bs for bs in branch_services if bs["service_template_id"] == template["id"])

    walk_in = client.post(
        f"/api/v1/businesses/{business_id}/customers",
        json={"first_name": "Walk", "last_name": "In", "mobile_number": "9000000000"},
        headers=_auth(owner_token),
    ).json()

    return {
        "business_id": business_id, "owner_token": owner_token, "admin_token": admin_token,
        "branch": branch, "resource": resource, "branch_service": branch_service, "customer": walk_in,
    }


def _create_booking(setup, start_time="09:00:00"):
    response = client.post(
        f"/api/v1/branches/{setup['branch']['id']}/bookings",
        json={
            "customer_id": setup["customer"]["id"],
            "branch_service_id": setup["branch_service"]["id"],
            "booking_date": str(BOOKING_DATE),
            "start_time": start_time,
        },
        headers=_auth(setup["owner_token"]),
    )
    assert response.status_code == 200, response.text
    return response.json()


# -----------------------------
# Business Owner Reports
# -----------------------------

def test_business_reports_returns_expected_counts():
    setup = _bookable_setup()
    booking = _create_booking(setup)
    client.post(f"/api/v1/bookings/{booking['id']}/complete", headers=_auth(setup["owner_token"]))

    response = client.get(f"/api/v1/businesses/{setup['business_id']}/reports", headers=_auth(setup["owner_token"]))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_bookings"] == 1
    assert body["completed_bookings"] == 1
    assert body["cancelled_bookings"] == 0
    assert body["active_branches"] == 1
    assert body["active_resources"] == 1


def test_business_reports_rejected_for_non_owner():
    setup = _bookable_setup()
    unique = uuid.uuid4().hex[:8]
    other = f"reportintruder_{unique}"
    _register_business(username=other, email=f"{other}@example.com")
    other_token = _login(other)

    response = client.get(f"/api/v1/businesses/{setup['business_id']}/reports", headers=_auth(other_token))
    assert response.status_code == 403


# -----------------------------
# Branch Manager Daily Reports
# -----------------------------

def test_branch_daily_report_returns_expected_metrics():
    setup = _bookable_setup()
    booking = _create_booking(setup)

    response = client.get(
        f"/api/v1/branches/{setup['branch']['id']}/reports/daily",
        params={"report_date": str(BOOKING_DATE)},
        headers=_auth(setup["owner_token"]),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["daily_bookings"] == 1
    assert len(body["resource_utilization"]) == 1
    assert body["resource_utilization"][0]["resource_id"] == setup["resource"]["id"]
    assert body["resource_utilization"][0]["booking_count"] == 1
    assert len(body["service_popularity"]) == 1
    assert body["service_popularity"][0]["booking_count"] == 1


def test_branch_daily_report_rejected_for_unrelated_user():
    setup = _bookable_setup()
    unique = uuid.uuid4().hex[:8]
    other = f"dailyintruder_{unique}"
    _register_business(username=other, email=f"{other}@example.com")
    other_token = _login(other)

    response = client.get(
        f"/api/v1/branches/{setup['branch']['id']}/reports/daily", headers=_auth(other_token)
    )
    assert response.status_code == 403


# -----------------------------
# Business Owner Audit History (M9 Phase 6c)
# -----------------------------

def test_owner_can_view_own_business_audit_history():
    business_id, owner_token, admin_token = _register_and_approve_business()

    response = client.get(
        f"/api/v1/businesses/{business_id}/audit-logs",
        params={"action": "BUSINESS_APPROVED"},
        headers=_auth(owner_token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    for key in ("items", "total", "page", "page_size", "total_pages"):
        assert key in body
    assert body["total"] >= 1
    assert all(row["business_id"] == business_id for row in body["items"])


def test_owner_cannot_view_another_business_audit_history():
    business_id, owner_token, admin_token = _register_and_approve_business()
    unique = uuid.uuid4().hex[:8]
    other = f"audithistoryintruder_{unique}"
    _register_business(username=other, email=f"{other}@example.com")
    other_token = _login(other)

    response = client.get(f"/api/v1/businesses/{business_id}/audit-logs", headers=_auth(other_token))
    assert response.status_code == 403


# -----------------------------
# Platform Admin: Audit Logs, Notifications, Analytics
# -----------------------------

def test_platform_admin_can_list_audit_logs():
    business_id, owner_token, admin_token = _register_and_approve_business()

    response = client.get(
        "/api/v1/admin/audit-logs",
        params={"business_id": business_id, "action": "BUSINESS_APPROVED"},
        headers=_auth(admin_token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    for key in ("items", "total", "page", "page_size", "total_pages"):
        assert key in body
    assert body["total"] >= 1
    assert body["items"][0]["action"] == "BUSINESS_APPROVED"


def test_non_admin_cannot_list_audit_logs():
    _, owner_token, _ = _register_and_approve_business()
    response = client.get("/api/v1/admin/audit-logs", headers=_auth(owner_token))
    assert response.status_code == 403


def test_audit_log_filter_options_reflect_real_data():
    """Manual-testing follow-up fix: Audit Log entity-type/action filters
    are dropdowns of real distinct values, not free text."""
    business_id, owner_token, admin_token = _register_and_approve_business()

    response = client.get("/api/v1/admin/audit-logs/filters", headers=_auth(admin_token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert "Business" in body["entity_types"]
    assert "BUSINESS_APPROVED" in body["actions"]
    assert "BUSINESS_REGISTERED" in body["actions"]

    filtered = client.get(
        "/api/v1/admin/audit-logs",
        params={"entity_type": "Business", "action": "BUSINESS_APPROVED"},
        headers=_auth(admin_token),
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] >= 1
    assert all(row["entity_type"] == "Business" and row["action"] == "BUSINESS_APPROVED" for row in filtered.json()["items"])


def test_non_admin_cannot_view_audit_log_filter_options():
    _, owner_token, _ = _register_and_approve_business()
    response = client.get("/api/v1/admin/audit-logs/filters", headers=_auth(owner_token))
    assert response.status_code == 403


def test_platform_admin_can_list_notifications():
    business_id, owner_token, admin_token = _register_and_approve_business()

    response = client.get(
        "/api/v1/admin/notifications",
        params={"business_id": business_id, "notification_type": "BusinessApproved"},
        headers=_auth(admin_token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    for key in ("items", "total", "page", "page_size", "total_pages"):
        assert key in body
    assert body["total"] >= 1


def test_platform_admin_can_view_platform_analytics():
    _, owner_token, admin_token = _register_and_approve_business()

    response = client.get("/api/v1/admin/platform-analytics", headers=_auth(admin_token))
    assert response.status_code == 200, response.text
    body = response.json()
    for key in ("total_businesses", "pending_business_approvals", "active_businesses", "active_branches"):
        assert key in body
    assert body["total_businesses"] >= 1


def test_non_admin_cannot_view_platform_analytics():
    _, owner_token, _ = _register_and_approve_business()
    response = client.get("/api/v1/admin/platform-analytics", headers=_auth(owner_token))
    assert response.status_code == 403


# -----------------------------
# Resource User self-scoped bookings
# -----------------------------

def test_resource_user_can_view_own_bookings_only():
    # ID-014 lifecycle order: Create (requires_login=True) -> Invite/Accept
    # (links the user) -> Activate -> only then is the resource bookable.
    business_id, owner_token, admin_token = _register_and_approve_business()
    branch = _create_branch(business_id, owner_token, admin_token)
    unique = uuid.uuid4().hex[:8]

    category = client.post(
        f"/api/v1/businesses/{business_id}/resource-categories",
        json={"category_name": f"Category {unique}"},
        headers=_auth(owner_token),
    ).json()
    resource = client.post(
        f"/api/v1/branches/{branch['id']}/resources",
        json={"resource_category_id": category["id"], "resource_name": f"Resource {unique}", "requires_login": True},
        headers=_auth(owner_token),
    ).json()

    email = f"reportruser_{unique}@example.com"
    captured = {}
    import routers.resources as resources_router

    def fake_send(email_arg, token, role_code, business_name):
        captured["token"] = token

    original = resources_router.send_staff_invitation_email
    resources_router.send_staff_invitation_email = fake_send
    try:
        invite = client.post(
            f"/api/v1/businesses/{business_id}/resources/{resource['id']}/invite-user",
            json={"email": email},
            headers=_auth(owner_token),
        )
        assert invite.status_code == 200, invite.text
    finally:
        resources_router.send_staff_invitation_email = original

    accept = client.post(
        "/api/v1/auth/accept-invitation",
        json={"token": captured["token"], "username": f"reportruser_{unique}", "password": "Testpass123!"},
    )
    assert accept.status_code == 200, accept.text
    resource_user_token = _login(f"reportruser_{unique}")

    activate = client.post(f"/api/v1/resources/{resource['id']}/activate", headers=_auth(owner_token))
    assert activate.status_code == 200, activate.text
    hours = client.put(
        f"/api/v1/resources/{resource['id']}/working-hours",
        json={"hours": [{"weekday": BOOKING_DATE.weekday(), "opening_time": "09:00:00", "closing_time": "17:00:00"}]},
        headers=_auth(owner_token),
    )
    assert hours.status_code == 200, hours.text

    template = client.post(
        f"/api/v1/businesses/{business_id}/service-templates",
        json={
            "name": f"Template {unique}", "default_duration": 30, "default_price": "100.00",
            "default_resource_category_ids": [category["id"]],
        },
        headers=_auth(owner_token),
    ).json()
    branch_services = client.get(
        f"/api/v1/businesses/{business_id}/branch-services", headers=_auth(owner_token)
    ).json()["items"]
    branch_service = next(bs for bs in branch_services if bs["service_template_id"] == template["id"])

    walk_in = client.post(
        f"/api/v1/businesses/{business_id}/customers",
        json={"first_name": "Walk", "last_name": "In", "mobile_number": "9000000001"},
        headers=_auth(owner_token),
    ).json()

    booking = client.post(
        f"/api/v1/branches/{branch['id']}/bookings",
        json={
            "customer_id": walk_in["id"],
            "branch_service_id": branch_service["id"],
            "booking_date": str(BOOKING_DATE),
            "start_time": "09:00:00",
        },
        headers=_auth(owner_token),
    )
    assert booking.status_code == 200, booking.text
    booking = booking.json()

    response = client.get("/api/v1/resource/bookings", headers=_auth(resource_user_token))
    assert response.status_code == 200, response.text
    ids = [b["id"] for b in response.json()]
    assert booking["id"] in ids


def test_user_without_linked_resource_is_rejected():
    setup = _bookable_setup()
    response = client.get("/api/v1/resource/bookings", headers=_auth(setup["owner_token"]))
    assert response.status_code == 403
