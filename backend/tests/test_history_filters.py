"""M9 follow-up fix: Branch/date-range filters + pagination on Booking
History, Audit History, and Notifications for Business Owner and Branch
Manager, plus Customer Booking History pagination — and the authorization/
tenant-isolation rules around all of it (including that HR and Resource
User get none of it)."""

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
    admin_username = f"histadmin_{unique}"
    _register_business(username=admin_username, email=f"{admin_username}@example.com")
    _promote_to_platform_admin(admin_username)
    admin_token = _login(admin_username)

    owner_username = f"histowner_{unique}"
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


def _invite_and_accept(business_id, owner_token, role_code, branch_id=None):
    import routers.staff as staff_router

    unique = uuid.uuid4().hex[:8]
    captured = {}

    def fake_send(email, token, role_code_arg, business_name):
        captured["token"] = token

    original = staff_router.send_staff_invitation_email
    staff_router.send_staff_invitation_email = fake_send
    try:
        payload = {"email": f"{role_code.lower()}_{unique}@example.com", "role_code": role_code}
        if branch_id:
            payload["branch_id"] = branch_id
        invite = client.post(f"/api/v1/businesses/{business_id}/staff/invite", json=payload, headers=_auth(owner_token))
        assert invite.status_code == 200, invite.text
    finally:
        staff_router.send_staff_invitation_email = original

    username = f"{role_code.lower()}user_{unique}"
    accept = client.post(
        "/api/v1/auth/accept-invitation",
        json={"token": captured["token"], "username": username, "password": "Testpass123!"},
    )
    assert accept.status_code == 200, accept.text
    return _login(username)


def _invite_and_accept_resource_user(business_id, owner_token, resource_id):
    import routers.resources as resources_router

    unique = uuid.uuid4().hex[:8]
    captured = {}

    def fake_send(email, token, role_code, business_name):
        captured["token"] = token

    original = resources_router.send_staff_invitation_email
    resources_router.send_staff_invitation_email = fake_send
    try:
        invite = client.post(
            f"/api/v1/businesses/{business_id}/resources/{resource_id}/invite-user",
            json={"email": f"ruser_{unique}@example.com"},
            headers=_auth(owner_token),
        )
        assert invite.status_code == 200, invite.text
    finally:
        resources_router.send_staff_invitation_email = original

    username = f"ruser_{unique}"
    accept = client.post(
        "/api/v1/auth/accept-invitation",
        json={"token": captured["token"], "username": username, "password": "Testpass123!"},
    )
    assert accept.status_code == 200, accept.text
    return _login(username)


def _bookable_setup(business_id, owner_token, branch):
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
    client.post(f"/api/v1/resources/{resource['id']}/activate", headers=_auth(owner_token))
    client.put(
        f"/api/v1/resources/{resource['id']}/working-hours",
        json={"hours": [{"weekday": BOOKING_DATE.weekday(), "opening_time": "09:00:00", "closing_time": "17:00:00"}]},
        headers=_auth(owner_token),
    )
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
    # Templates inherit to every branch in the business (ID-023), so filter
    # by branch_id too, not just service_template_id, to get *this* branch's copy.
    branch_service = next(
        bs for bs in branch_services
        if bs["service_template_id"] == template["id"] and bs["branch_id"] == branch["id"]
    )
    customer = client.post(
        f"/api/v1/businesses/{business_id}/customers",
        json={"first_name": "Walk", "last_name": "In", "mobile_number": f"9{unique[:9]}"},
        headers=_auth(owner_token),
    ).json()
    return resource, branch_service, customer


def _create_booking(branch_id, owner_token, branch_service, customer, booking_date=None):
    response = client.post(
        f"/api/v1/branches/{branch_id}/bookings",
        json={
            "customer_id": customer["id"], "branch_service_id": branch_service["id"],
            "booking_date": str(booking_date or BOOKING_DATE), "start_time": "09:00:00",
        },
        headers=_auth(owner_token),
    )
    assert response.status_code == 200, response.text
    return response.json()


# -----------------------------
# Booking History
# -----------------------------

def test_owner_booking_history_supports_branch_and_date_range_filter():
    business_id, owner_token, admin_token = _register_and_approve_business()
    branch_1 = _create_branch(business_id, owner_token, admin_token, "Branch One")
    branch_2 = _create_branch(business_id, owner_token, admin_token, "Branch Two")
    _, bs1, cust1 = _bookable_setup(business_id, owner_token, branch_1)
    _, bs2, cust2 = _bookable_setup(business_id, owner_token, branch_2)
    booking1 = _create_booking(branch_1["id"], owner_token, bs1, cust1)
    booking2 = _create_booking(branch_2["id"], owner_token, bs2, cust2)

    response = client.get(
        f"/api/v1/businesses/{business_id}/bookings",
        params={"branch_id": branch_1["id"], "date_from": str(BOOKING_DATE), "date_to": str(BOOKING_DATE)},
        headers=_auth(owner_token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    ids = [b["id"] for b in body["items"]]
    assert booking1["id"] in ids
    assert booking2["id"] not in ids

    outside_range = client.get(
        f"/api/v1/businesses/{business_id}/bookings",
        params={"date_from": str(BOOKING_DATE + timedelta(days=1))},
        headers=_auth(owner_token),
    )
    assert outside_range.status_code == 200
    assert booking1["id"] not in [b["id"] for b in outside_range.json()["items"]]


def test_owner_booking_history_branch_filter_rejects_other_business_branch():
    business_id, owner_token, admin_token = _register_and_approve_business()
    other_business_id, other_owner_token, other_admin_token = _register_and_approve_business()
    other_branch = _create_branch(other_business_id, other_owner_token, other_admin_token)

    response = client.get(
        f"/api/v1/businesses/{business_id}/bookings",
        params={"branch_id": other_branch["id"]},
        headers=_auth(owner_token),
    )
    assert response.status_code == 400


def test_branch_manager_booking_history_supports_date_range_and_pagination():
    business_id, owner_token, admin_token = _register_and_approve_business()
    branch = _create_branch(business_id, owner_token, admin_token)
    _, bs, cust = _bookable_setup(business_id, owner_token, branch)
    booking = _create_booking(branch["id"], owner_token, bs, cust)

    bm_token = _invite_and_accept(business_id, owner_token, "BRANCH_MANAGER", branch["id"])

    response = client.get(
        f"/api/v1/branches/{branch['id']}/booking-history",
        params={"date_from": str(BOOKING_DATE), "date_to": str(BOOKING_DATE), "page": 1, "page_size": 20},
        headers=_auth(bm_token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    for key in ("items", "total", "page", "page_size", "total_pages"):
        assert key in body
    assert booking["id"] in [b["id"] for b in body["items"]]


def test_branch_manager_cannot_view_another_branch_booking_history():
    business_id, owner_token, admin_token = _register_and_approve_business()
    branch_1 = _create_branch(business_id, owner_token, admin_token, "Branch One")
    branch_2 = _create_branch(business_id, owner_token, admin_token, "Branch Two")

    bm_token = _invite_and_accept(business_id, owner_token, "BRANCH_MANAGER", branch_1["id"])

    response = client.get(f"/api/v1/branches/{branch_2['id']}/booking-history", headers=_auth(bm_token))
    assert response.status_code == 403


def test_customer_booking_history_supports_date_range_and_pagination_and_isolation():
    business_id, owner_token, admin_token = _register_and_approve_business()
    branch = _create_branch(business_id, owner_token, admin_token)
    _, bs, _ = _bookable_setup(business_id, owner_token, branch)

    unique = uuid.uuid4().hex[:8]
    cust_email = f"histcust_{unique}@example.com"
    reg = client.post("/api/v1/customers/register", json={
        "first_name": "Hist", "last_name": "Customer", "email": cust_email,
        "mobile_number": f"8{unique[:9]}", "password": "Testpass123!",
    })
    assert reg.status_code == 200, reg.text
    cust_token = _login(cust_email)

    booking = client.post(
        "/api/v1/customer/bookings",
        json={"branch_service_id": bs["id"], "booking_date": str(BOOKING_DATE), "start_time": "09:00:00"},
        headers=_auth(cust_token),
    )
    assert booking.status_code == 200, booking.text

    response = client.get(
        "/api/v1/customer/bookings",
        params={"date_from": str(BOOKING_DATE), "date_to": str(BOOKING_DATE), "page": 1, "page_size": 20},
        headers=_auth(cust_token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    for key in ("items", "total", "page", "page_size", "total_pages"):
        assert key in body
    assert booking.json()["id"] in [b["id"] for b in body["items"]]

    # Isolation: a second customer sees none of the first customer's bookings.
    other_email = f"histcust2_{unique}@example.com"
    client.post("/api/v1/customers/register", json={
        "first_name": "Other", "last_name": "Customer", "email": other_email,
        "mobile_number": f"7{unique[:9]}", "password": "Testpass123!",
    })
    other_token = _login(other_email)
    other_response = client.get("/api/v1/customer/bookings", headers=_auth(other_token))
    assert other_response.status_code == 200
    assert other_response.json()["total"] == 0


# -----------------------------
# Audit History
# -----------------------------

def test_owner_audit_history_supports_branch_filter():
    business_id, owner_token, admin_token = _register_and_approve_business()
    branch_1 = _create_branch(business_id, owner_token, admin_token, "Branch One")
    _create_branch(business_id, owner_token, admin_token, "Branch Two")

    response = client.get(
        f"/api/v1/businesses/{business_id}/audit-logs",
        params={"branch_id": branch_1["id"], "action": "BRANCH_APPROVED"},
        headers=_auth(owner_token),
    )
    assert response.status_code == 200, response.text
    assert response.json()["total"] >= 1


def test_owner_audit_history_branch_filter_rejects_other_business_branch():
    business_id, owner_token, admin_token = _register_and_approve_business()
    other_business_id, other_owner_token, other_admin_token = _register_and_approve_business()
    other_branch = _create_branch(other_business_id, other_owner_token, other_admin_token)

    response = client.get(
        f"/api/v1/businesses/{business_id}/audit-logs",
        params={"branch_id": other_branch["id"]},
        headers=_auth(owner_token),
    )
    assert response.status_code == 400


def test_branch_manager_can_view_own_branch_audit_history_but_not_another():
    business_id, owner_token, admin_token = _register_and_approve_business()
    branch_1 = _create_branch(business_id, owner_token, admin_token, "Branch One")
    branch_2 = _create_branch(business_id, owner_token, admin_token, "Branch Two")

    bm_token = _invite_and_accept(business_id, owner_token, "BRANCH_MANAGER", branch_1["id"])

    own = client.get(f"/api/v1/branches/{branch_1['id']}/audit-logs", headers=_auth(bm_token))
    assert own.status_code == 200, own.text
    assert any(row["action"] == "BRANCH_APPROVED" for row in own.json()["items"])

    other = client.get(f"/api/v1/branches/{branch_2['id']}/audit-logs", headers=_auth(bm_token))
    assert other.status_code == 403


def test_branch_audit_log_filter_options_scoped_to_branch():
    business_id, owner_token, admin_token = _register_and_approve_business()
    branch = _create_branch(business_id, owner_token, admin_token)
    bm_token = _invite_and_accept(business_id, owner_token, "BRANCH_MANAGER", branch["id"])

    response = client.get(f"/api/v1/branches/{branch['id']}/audit-logs/filters", headers=_auth(bm_token))
    assert response.status_code == 200, response.text
    assert "BRANCH_APPROVED" in response.json()["actions"]
    # A business-only action (never tied to this branch) should not appear.
    assert "BUSINESS_APPROVED" not in response.json()["actions"]


# -----------------------------
# Notifications
# -----------------------------

def test_owner_notifications_supports_branch_filter_and_date_range():
    business_id, owner_token, admin_token = _register_and_approve_business()
    branch = _create_branch(business_id, owner_token, admin_token)

    response = client.get(
        f"/api/v1/businesses/{business_id}/notifications",
        params={"branch_id": branch["id"], "date_from": str(date.today() - timedelta(days=1))},
        headers=_auth(owner_token),
    )
    assert response.status_code == 200, response.text
    assert response.json()["total"] >= 1
    assert any(n["notification_type"] == "BranchApproved" for n in response.json()["items"])


def test_branch_manager_can_view_own_branch_notifications_but_not_another():
    business_id, owner_token, admin_token = _register_and_approve_business()
    branch_1 = _create_branch(business_id, owner_token, admin_token, "Branch One")
    branch_2 = _create_branch(business_id, owner_token, admin_token, "Branch Two")

    bm_token = _invite_and_accept(business_id, owner_token, "BRANCH_MANAGER", branch_1["id"])

    own = client.get(f"/api/v1/branches/{branch_1['id']}/notifications", headers=_auth(bm_token))
    assert own.status_code == 200, own.text
    assert any(n["notification_type"] == "BranchApproved" for n in own.json()["items"])

    other = client.get(f"/api/v1/branches/{branch_2['id']}/notifications", headers=_auth(bm_token))
    assert other.status_code == 403


# -----------------------------
# HR and Resource User must be rejected from all of the above
# -----------------------------

def test_hr_and_resource_user_cannot_access_any_history_or_notification_endpoints():
    business_id, owner_token, admin_token = _register_and_approve_business()
    branch = _create_branch(business_id, owner_token, admin_token)
    _bookable_setup(business_id, owner_token, branch)

    unique = uuid.uuid4().hex[:8]
    category = client.post(
        f"/api/v1/businesses/{business_id}/resource-categories",
        json={"category_name": f"Category {unique}"},
        headers=_auth(owner_token),
    ).json()
    login_resource = client.post(
        f"/api/v1/branches/{branch['id']}/resources",
        json={"resource_category_id": category["id"], "resource_name": f"LoginResource {unique}", "requires_login": True},
        headers=_auth(owner_token),
    ).json()

    hr_token = _invite_and_accept(business_id, owner_token, "HR_USER")
    ru_token = _invite_and_accept_resource_user(business_id, owner_token, login_resource["id"])

    for token, label in [(hr_token, "HR"), (ru_token, "Resource User")]:
        r = client.get(f"/api/v1/businesses/{business_id}/audit-logs", headers=_auth(token))
        assert r.status_code == 403, f"{label} audit-logs: {r.status_code}"
        r = client.get(f"/api/v1/businesses/{business_id}/notifications", headers=_auth(token))
        assert r.status_code == 403, f"{label} notifications: {r.status_code}"
        r = client.get(f"/api/v1/branches/{branch['id']}/audit-logs", headers=_auth(token))
        assert r.status_code == 403, f"{label} branch audit-logs: {r.status_code}"
        r = client.get(f"/api/v1/branches/{branch['id']}/notifications", headers=_auth(token))
        assert r.status_code == 403, f"{label} branch notifications: {r.status_code}"
        r = client.get(f"/api/v1/branches/{branch['id']}/booking-history", headers=_auth(token))
        assert r.status_code == 403, f"{label} booking-history: {r.status_code}"
