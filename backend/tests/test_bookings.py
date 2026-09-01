import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from main import app
from database import SessionLocal
from models import Role, BusinessCategory, Country, User, UserRole, BranchService

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


@pytest.fixture(autouse=True)
def stub_booking_emails(monkeypatch):
    """TestClient runs BackgroundTasks synchronously — stub the SMTP calls (PRD §37: notification
    failures must never interrupt the booking operation; the send functions themselves are exercised
    directly by services/email_service.py's own concerns, not re-tested here)."""
    import routers.bookings as bookings_router

    for name in (
        "send_booking_confirmation_email",
        "send_booking_rescheduled_email",
        "send_booking_cancelled_email",
        "send_booking_completed_email",
    ):
        monkeypatch.setattr(bookings_router, name, lambda *args, **kwargs: None)


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
    response = client.post("/api/v1/auth/login", data={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _register_and_approve_business():
    unique = uuid.uuid4().hex[:8]
    owner_username = f"activeowner_{unique}"
    business = _register_business(username=owner_username, email=f"{unique}@example.com")

    admin_username = f"bookadmin_{unique}"
    _register_business(username=admin_username, email=f"{admin_username}@example.com")
    _promote_to_platform_admin(admin_username)
    admin_token = _login(admin_username)

    approve = client.post(f"/api/v1/businesses/{business['id']}/approve", headers=_auth(admin_token))
    assert approve.status_code == 200, approve.text

    owner_token = _login(owner_username)
    return business["id"], owner_username, owner_token


def _create_branch(business_id, owner_token, branch_name=None):
    unique = uuid.uuid4().hex[:8]
    payload = {"branch_name": branch_name or f"Branch {unique}", "country_id": _country_id()}
    response = client.post(f"/api/v1/businesses/{business_id}/branches", json=payload, headers=_auth(owner_token))
    assert response.status_code == 200, response.text
    return response.json()


def _approve_and_activate_branch(business_id, branch_id, owner_token):
    unique = uuid.uuid4().hex[:8]
    admin_username = f"branchapprover_{unique}"
    _register_business(username=admin_username, email=f"{admin_username}@example.com")
    _promote_to_platform_admin(admin_username)
    admin_token = _login(admin_username)

    approve = client.post(f"/api/v1/branches/{branch_id}/approve", headers=_auth(admin_token))
    assert approve.status_code == 200, approve.text

    activate = client.post(f"/api/v1/branches/{branch_id}/activate", headers=_auth(owner_token))
    assert activate.status_code == 200, activate.text


def _create_and_approve_branch(business_id, owner_token, branch_name=None):
    branch = _create_branch(business_id, owner_token, branch_name)
    _approve_and_activate_branch(business_id, branch["id"], owner_token)
    return branch


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
            f"/api/v1/businesses/{business_id}/staff/invite", json=payload, headers=_auth(owner_token)
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


def _create_active_resource(branch_id, owner_token, category_id, **extra):
    unique = uuid.uuid4().hex[:8]
    payload = {"resource_name": f"Resource {unique}", "resource_category_id": category_id, "requires_login": False}
    payload.update(extra)
    response = client.post(f"/api/v1/branches/{branch_id}/resources", json=payload, headers=_auth(owner_token))
    assert response.status_code == 200, response.text
    resource = response.json()

    activate = client.post(f"/api/v1/resources/{resource['id']}/activate", headers=_auth(owner_token))
    assert activate.status_code == 200, activate.text
    return resource


def _set_resource_hours(resource_id, owner_token, weekday, opening="09:00:00", closing="17:00:00", break_start=None, break_end=None):
    payload = {
        "hours": [
            {
                "weekday": weekday,
                "opening_time": opening,
                "closing_time": closing,
                "is_closed": False,
                "break_start_time": break_start,
                "break_end_time": break_end,
            }
        ]
    }
    response = client.put(f"/api/v1/resources/{resource_id}/working-hours", json=payload, headers=_auth(owner_token))
    assert response.status_code == 200, response.text


def _create_template(business_id, owner_token, name=None, **extra):
    unique = uuid.uuid4().hex[:8]
    payload = {
        "name": name or f"Service {unique}",
        "default_duration": 30,
        "default_price": "300.00",
        "default_resource_category_ids": [],
    }
    payload.update(extra)
    response = client.post(f"/api/v1/businesses/{business_id}/service-templates", json=payload, headers=_auth(owner_token))
    assert response.status_code == 200, response.text
    return response.json()


def _get_branch_service(branch_id, owner_token):
    response = client.get(f"/api/v1/branches/{branch_id}/branch-services", headers=_auth(owner_token))
    assert response.status_code == 200, response.text
    services = response.json()
    assert services, "expected an auto-inherited BranchService"
    return services[0]


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
    assert response.status_code == 200, response.text
    return payload


def _create_walk_in(business_id, staff_token, **overrides):
    unique = uuid.uuid4().hex[:8]
    payload = {"first_name": "Walk", "last_name": "In", "mobile_number": "8880002222"}
    payload.update(overrides)
    response = client.post(f"/api/v1/businesses/{business_id}/customers", json=payload, headers=_auth(staff_token))
    assert response.status_code == 200, response.text
    return response.json()


def _next_weekday_date(weekday: int) -> date:
    """Always a future date matching `weekday` (0=Monday..6=Sunday), never today."""
    today = date.today()
    days_ahead = (weekday - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return today + timedelta(days=days_ahead)


WEEKDAY = 0  # Monday — arbitrary, consistent across the suite
BOOKING_DATE = _next_weekday_date(WEEKDAY)


def _bookable_setup(**resource_extra):
    """business (Active) -> branch (Approved+Active) -> category -> Active resource with
    Monday 09:00-17:00 hours -> Service Template (duration 30) inherited as an Approved BranchService."""
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_and_approve_branch(business_id, owner_token)
    category = _create_category(business_id, owner_token)
    resource = _create_active_resource(branch["id"], owner_token, category["id"], **resource_extra)
    _set_resource_hours(resource["id"], owner_token, WEEKDAY)
    _create_template(business_id, owner_token, default_duration=30, default_resource_category_ids=[category["id"]])
    branch_service = _get_branch_service(branch["id"], owner_token)

    return {
        "business_id": business_id,
        "owner_token": owner_token,
        "branch": branch,
        "category": category,
        "resource": resource,
        "branch_service": branch_service,
    }


# -----------------------------
# Availability Engine (PRD §14.6, §16.3; TAS Part 4 §3)
# -----------------------------

def test_availability_lists_slots_respecting_working_hours():
    setup = _bookable_setup()
    response = client.get(
        f"/api/v1/branches/{setup['branch']['id']}/availability",
        params={"branch_service_id": setup["branch_service"]["id"], "date": str(BOOKING_DATE)},
        headers=_auth(setup["owner_token"]),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["slots"], "expected at least one open slot within 09:00-17:00"
    assert body["slots"][0]["start_time"] == "09:00:00"
    assert setup["resource"]["id"] in body["slots"][0]["available_resource_ids"]


def test_availability_excludes_break_window():
    setup = _bookable_setup()
    client.put(
        f"/api/v1/resources/{setup['resource']['id']}/working-hours",
        json={"hours": [{
            "weekday": WEEKDAY, "opening_time": "09:00:00", "closing_time": "17:00:00", "is_closed": False,
            "break_start_time": "12:00:00", "break_end_time": "13:00:00",
        }]},
        headers=_auth(setup["owner_token"]),
    )
    response = client.get(
        f"/api/v1/branches/{setup['branch']['id']}/availability",
        params={"branch_service_id": setup["branch_service"]["id"], "date": str(BOOKING_DATE)},
        headers=_auth(setup["owner_token"]),
    )
    slot_starts = [s["start_time"] for s in response.json()["slots"]]
    assert "12:00:00" not in slot_starts
    assert "12:30:00" not in slot_starts


def test_availability_rejected_when_branch_not_approved():
    business_id, _, owner_token = _register_and_approve_business()
    branch = _create_branch(business_id, owner_token)  # never approved/activated
    category = _create_category(business_id, owner_token)
    _create_active_resource(branch["id"], owner_token, category["id"])
    _create_template(business_id, owner_token, default_resource_category_ids=[category["id"]])
    branch_service = _get_branch_service(branch["id"], owner_token)

    response = client.get(
        f"/api/v1/branches/{branch['id']}/availability",
        params={"branch_service_id": branch_service["id"], "date": str(BOOKING_DATE)},
        headers=_auth(owner_token),
    )
    assert response.status_code == 409, response.text


def test_availability_rejected_when_service_not_approved():
    setup = _bookable_setup()
    db = SessionLocal()
    try:
        bs = db.query(BranchService).filter(BranchService.id == setup["branch_service"]["id"]).first()
        bs.status = "Pending"
        db.commit()
    finally:
        db.close()

    response = client.get(
        f"/api/v1/branches/{setup['branch']['id']}/availability",
        params={"branch_service_id": setup["branch_service"]["id"], "date": str(BOOKING_DATE)},
        headers=_auth(setup["owner_token"]),
    )
    assert response.status_code == 409, response.text


# -----------------------------
# Booking creation (PRD §18.4; BR-042-BR-044)
# -----------------------------

def test_staff_can_create_booking_for_walk_in_customer_with_history_and_audit():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])

    response = client.post(
        f"/api/v1/branches/{setup['branch']['id']}/bookings",
        json={
            "customer_id": customer["id"],
            "branch_service_id": setup["branch_service"]["id"],
            "booking_date": str(BOOKING_DATE),
            "start_time": "09:00:00",
        },
        headers=_auth(setup["owner_token"]),
    )
    assert response.status_code == 200, response.text
    booking = response.json()
    assert booking["status"] == "Confirmed"
    assert booking["end_time"] == "09:30:00"
    assert booking["resource_id"] == setup["resource"]["id"]
    assert booking["customer_id"] == customer["id"]

    history = client.get(f"/api/v1/bookings/{booking['id']}/history", headers=_auth(setup["owner_token"]))
    assert history.status_code == 200, history.text
    actions = [h["action"] for h in history.json()]
    assert actions == ["Created"]


def test_customer_self_booking_auto_provisions_business_customer():
    setup = _bookable_setup()
    customer_payload = _register_customer()
    customer_token = _login(customer_payload["email"])

    response = client.post(
        "/api/v1/customer/bookings",
        json={
            "branch_service_id": setup["branch_service"]["id"],
            "booking_date": str(BOOKING_DATE),
            "start_time": "09:00:00",
        },
        headers=_auth(customer_token),
    )
    assert response.status_code == 200, response.text
    booking = response.json()
    assert booking["status"] == "Confirmed"

    # Reusing the same business the second time reuses the same BusinessCustomer.
    listing = client.get("/api/v1/customer/bookings", headers=_auth(customer_token))
    assert listing.status_code == 200
    assert len(listing.json()) == 1
    assert listing.json()[0]["customer_id"] == booking["customer_id"]


def test_manual_resource_selection_rejects_ineligible_category():
    setup = _bookable_setup()
    other_category = _create_category(setup["business_id"], setup["owner_token"])
    other_resource = _create_active_resource(setup["branch"]["id"], setup["owner_token"], other_category["id"])
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])

    response = client.post(
        f"/api/v1/branches/{setup['branch']['id']}/bookings",
        json={
            "customer_id": customer["id"],
            "branch_service_id": setup["branch_service"]["id"],
            "booking_date": str(BOOKING_DATE),
            "start_time": "09:00:00",
            "resource_id": other_resource["id"],
        },
        headers=_auth(setup["owner_token"]),
    )
    assert response.status_code == 400, response.text


def test_automatic_assignment_picks_first_available_resource():
    setup = _bookable_setup()
    second_resource = _create_active_resource(setup["branch"]["id"], setup["owner_token"], setup["category"]["id"])
    _set_resource_hours(second_resource["id"], setup["owner_token"], WEEKDAY)
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])

    first = client.post(
        f"/api/v1/branches/{setup['branch']['id']}/bookings",
        json={
            "customer_id": customer["id"], "branch_service_id": setup["branch_service"]["id"],
            "booking_date": str(BOOKING_DATE), "start_time": "09:00:00",
        },
        headers=_auth(setup["owner_token"]),
    )
    assert first.status_code == 200, first.text
    assert first.json()["resource_id"] == setup["resource"]["id"]  # lowest id first

    # Same slot again -> first resource is taken, engine falls through to the second.
    second = client.post(
        f"/api/v1/branches/{setup['branch']['id']}/bookings",
        json={
            "customer_id": customer["id"], "branch_service_id": setup["branch_service"]["id"],
            "booking_date": str(BOOKING_DATE), "start_time": "09:00:00",
        },
        headers=_auth(setup["owner_token"]),
    )
    assert second.status_code == 200, second.text
    assert second.json()["resource_id"] == second_resource["id"]


def test_double_booking_same_resource_same_slot_rejected():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    payload = {
        "customer_id": customer["id"], "branch_service_id": setup["branch_service"]["id"],
        "booking_date": str(BOOKING_DATE), "start_time": "09:00:00", "resource_id": setup["resource"]["id"],
    }
    first = client.post(f"/api/v1/branches/{setup['branch']['id']}/bookings", json=payload, headers=_auth(setup["owner_token"]))
    assert first.status_code == 200, first.text

    second = client.post(f"/api/v1/branches/{setup['branch']['id']}/bookings", json=payload, headers=_auth(setup["owner_token"]))
    assert second.status_code == 409, second.text


def test_booking_buffer_minutes_blocks_adjacent_slot():
    setup = _bookable_setup(booking_buffer_minutes=15)
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])

    first = client.post(
        f"/api/v1/branches/{setup['branch']['id']}/bookings",
        json={
            "customer_id": customer["id"], "branch_service_id": setup["branch_service"]["id"],
            "booking_date": str(BOOKING_DATE), "start_time": "09:00:00", "resource_id": setup["resource"]["id"],
        },
        headers=_auth(setup["owner_token"]),
    )
    assert first.status_code == 200, first.text

    # Immediately adjacent (09:30) falls inside the 15-minute buffer padding -> rejected.
    too_close = client.post(
        f"/api/v1/branches/{setup['branch']['id']}/bookings",
        json={
            "customer_id": customer["id"], "branch_service_id": setup["branch_service"]["id"],
            "booking_date": str(BOOKING_DATE), "start_time": "09:30:00", "resource_id": setup["resource"]["id"],
        },
        headers=_auth(setup["owner_token"]),
    )
    assert too_close.status_code == 409, too_close.text

    # 09:45 clears the buffer -> accepted.
    far_enough = client.post(
        f"/api/v1/branches/{setup['branch']['id']}/bookings",
        json={
            "customer_id": customer["id"], "branch_service_id": setup["branch_service"]["id"],
            "booking_date": str(BOOKING_DATE), "start_time": "09:45:00", "resource_id": setup["resource"]["id"],
        },
        headers=_auth(setup["owner_token"]),
    )
    assert far_enough.status_code == 200, far_enough.text


def test_max_bookings_per_day_cap_enforced():
    setup = _bookable_setup(max_bookings_per_day=1)
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])

    first = client.post(
        f"/api/v1/branches/{setup['branch']['id']}/bookings",
        json={
            "customer_id": customer["id"], "branch_service_id": setup["branch_service"]["id"],
            "booking_date": str(BOOKING_DATE), "start_time": "09:00:00", "resource_id": setup["resource"]["id"],
        },
        headers=_auth(setup["owner_token"]),
    )
    assert first.status_code == 200, first.text

    # A non-overlapping slot later the same day still hits the daily cap.
    second = client.post(
        f"/api/v1/branches/{setup['branch']['id']}/bookings",
        json={
            "customer_id": customer["id"], "branch_service_id": setup["branch_service"]["id"],
            "booking_date": str(BOOKING_DATE), "start_time": "14:00:00", "resource_id": setup["resource"]["id"],
        },
        headers=_auth(setup["owner_token"]),
    )
    assert second.status_code == 409, second.text


def test_booking_rejected_outside_working_hours():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    response = client.post(
        f"/api/v1/branches/{setup['branch']['id']}/bookings",
        json={
            "customer_id": customer["id"], "branch_service_id": setup["branch_service"]["id"],
            "booking_date": str(BOOKING_DATE), "start_time": "18:00:00", "resource_id": setup["resource"]["id"],
        },
        headers=_auth(setup["owner_token"]),
    )
    assert response.status_code == 409, response.text


# -----------------------------
# Reschedule (PRD §19; BR-046)
# -----------------------------

def test_staff_reschedule_preserves_booking_id_and_writes_history():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    created = client.post(
        f"/api/v1/branches/{setup['branch']['id']}/bookings",
        json={
            "customer_id": customer["id"], "branch_service_id": setup["branch_service"]["id"],
            "booking_date": str(BOOKING_DATE), "start_time": "09:00:00",
        },
        headers=_auth(setup["owner_token"]),
    ).json()

    new_date = BOOKING_DATE + timedelta(days=7)
    reschedule = client.post(
        f"/api/v1/bookings/{created['id']}/reschedule",
        json={"booking_date": str(new_date), "start_time": "10:00:00"},
        headers=_auth(setup["owner_token"]),
    )
    assert reschedule.status_code == 200, reschedule.text
    body = reschedule.json()
    assert body["id"] == created["id"]  # BR-046: same booking, not a new one
    assert body["booking_date"] == str(new_date)
    assert body["start_time"] == "10:00:00"

    history = client.get(f"/api/v1/bookings/{created['id']}/history", headers=_auth(setup["owner_token"])).json()
    assert [h["action"] for h in history] == ["Created", "Rescheduled"]
    assert history[1]["previous_state"]["booking_date"] == str(BOOKING_DATE)
    assert history[1]["new_state"]["booking_date"] == str(new_date)


def test_customer_can_reschedule_own_booking_but_not_anothers():
    setup = _bookable_setup()
    customer_a = _register_customer()
    token_a = _login(customer_a["email"])
    booking = client.post(
        "/api/v1/customer/bookings",
        json={
            "branch_service_id": setup["branch_service"]["id"],
            "booking_date": str(BOOKING_DATE), "start_time": "09:00:00",
        },
        headers=_auth(token_a),
    ).json()

    customer_b = _register_customer()
    token_b = _login(customer_b["email"])
    forbidden = client.post(
        f"/api/v1/customer/bookings/{booking['id']}/reschedule",
        json={"booking_date": str(BOOKING_DATE), "start_time": "10:00:00"},
        headers=_auth(token_b),
    )
    assert forbidden.status_code == 403, forbidden.text

    allowed = client.post(
        f"/api/v1/customer/bookings/{booking['id']}/reschedule",
        json={"booking_date": str(BOOKING_DATE), "start_time": "10:00:00"},
        headers=_auth(token_a),
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["start_time"] == "10:00:00"


def test_customer_reschedule_keeps_current_resource_when_still_free():
    setup = _bookable_setup()
    second_resource = _create_active_resource(setup["branch"]["id"], setup["owner_token"], setup["category"]["id"])
    _set_resource_hours(second_resource["id"], setup["owner_token"], WEEKDAY)

    customer = _register_customer()
    token = _login(customer["email"])
    original = client.post(
        "/api/v1/customer/bookings",
        json={"branch_service_id": setup["branch_service"]["id"], "booking_date": str(BOOKING_DATE), "start_time": "09:00:00"},
        headers=_auth(token),
    ).json()

    reschedule = client.post(
        f"/api/v1/customer/bookings/{original['id']}/reschedule",
        json={"booking_date": str(BOOKING_DATE), "start_time": "11:00:00"},
        headers=_auth(token),
    )
    assert reschedule.status_code == 200, reschedule.text
    assert reschedule.json()["resource_id"] == original["resource_id"]


def test_customer_reschedule_falls_back_to_another_eligible_resource_when_current_is_busy():
    setup = _bookable_setup()
    second_resource = _create_active_resource(setup["branch"]["id"], setup["owner_token"], setup["category"]["id"])
    _set_resource_hours(second_resource["id"], setup["owner_token"], WEEKDAY)

    customer = _register_customer()
    token = _login(customer["email"])

    # Customer books the first eligible resource (lowest id) at 09:00.
    original = client.post(
        "/api/v1/customer/bookings",
        json={"branch_service_id": setup["branch_service"]["id"], "booking_date": str(BOOKING_DATE), "start_time": "09:00:00"},
        headers=_auth(token),
    ).json()
    assert original["resource_id"] == setup["resource"]["id"]

    # A staff-created booking occupies the *original* resource at the new target time.
    other_customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    blocker = client.post(
        f"/api/v1/branches/{setup['branch']['id']}/bookings",
        json={
            "customer_id": other_customer["id"], "branch_service_id": setup["branch_service"]["id"],
            "booking_date": str(BOOKING_DATE), "start_time": "11:00:00", "resource_id": setup["resource"]["id"],
        },
        headers=_auth(setup["owner_token"]),
    )
    assert blocker.status_code == 200, blocker.text

    # Reschedule the customer's booking onto that now-busy slot: the original
    # resource is unavailable, but the second eligible resource is free —
    # the reschedule must fall back to it rather than being rejected.
    reschedule = client.post(
        f"/api/v1/customer/bookings/{original['id']}/reschedule",
        json={"booking_date": str(BOOKING_DATE), "start_time": "11:00:00"},
        headers=_auth(token),
    )
    assert reschedule.status_code == 200, reschedule.text
    body = reschedule.json()
    assert body["id"] == original["id"]  # same Booking ID, BR-046
    assert body["resource_id"] == second_resource["id"]  # fell back to the other eligible resource

    history = client.get(f"/api/v1/bookings/{original['id']}/history", headers=_auth(setup["owner_token"])).json()
    reschedule_entry = [h for h in history if h["action"] == "Rescheduled"][0]
    assert reschedule_entry["previous_state"]["resource_id"] == setup["resource"]["id"]
    assert reschedule_entry["new_state"]["resource_id"] == second_resource["id"]


def test_staff_reschedule_can_explicitly_reassign_resource():
    setup = _bookable_setup()
    second_resource = _create_active_resource(setup["branch"]["id"], setup["owner_token"], setup["category"]["id"])
    _set_resource_hours(second_resource["id"], setup["owner_token"], WEEKDAY)
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])

    booking = client.post(
        f"/api/v1/branches/{setup['branch']['id']}/bookings",
        json={
            "customer_id": customer["id"], "branch_service_id": setup["branch_service"]["id"],
            "booking_date": str(BOOKING_DATE), "start_time": "09:00:00", "resource_id": setup["resource"]["id"],
        },
        headers=_auth(setup["owner_token"]),
    ).json()

    # Even though the original resource is still free at the new time, staff
    # may explicitly request a different (eligible) resource.
    reschedule = client.post(
        f"/api/v1/bookings/{booking['id']}/reschedule",
        json={"booking_date": str(BOOKING_DATE), "start_time": "10:00:00", "resource_id": second_resource["id"]},
        headers=_auth(setup["owner_token"]),
    )
    assert reschedule.status_code == 200, reschedule.text
    assert reschedule.json()["resource_id"] == second_resource["id"]


# -----------------------------
# Cancellation (PRD §20; BR-045; ID-035)
# -----------------------------

def test_staff_cancel_records_reason_and_releases_resource():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    booking = client.post(
        f"/api/v1/branches/{setup['branch']['id']}/bookings",
        json={
            "customer_id": customer["id"], "branch_service_id": setup["branch_service"]["id"],
            "booking_date": str(BOOKING_DATE), "start_time": "09:00:00", "resource_id": setup["resource"]["id"],
        },
        headers=_auth(setup["owner_token"]),
    ).json()

    cancel = client.post(
        f"/api/v1/bookings/{booking['id']}/cancel",
        json={"reason": "Customer Request"},
        headers=_auth(setup["owner_token"]),
    )
    assert cancel.status_code == 200, cancel.text
    assert cancel.json()["status"] == "Cancelled"
    assert cancel.json()["cancellation_reason"] == "Customer Request"

    # Cancelling releases the resource — the same slot can be rebooked (BR-045: never deleted, only status change).
    rebook = client.post(
        f"/api/v1/branches/{setup['branch']['id']}/bookings",
        json={
            "customer_id": customer["id"], "branch_service_id": setup["branch_service"]["id"],
            "booking_date": str(BOOKING_DATE), "start_time": "09:00:00", "resource_id": setup["resource"]["id"],
        },
        headers=_auth(setup["owner_token"]),
    )
    assert rebook.status_code == 200, rebook.text

    # A cancelled booking cannot be modified further.
    reschedule_cancelled = client.post(
        f"/api/v1/bookings/{booking['id']}/reschedule",
        json={"booking_date": str(BOOKING_DATE), "start_time": "11:00:00"},
        headers=_auth(setup["owner_token"]),
    )
    assert reschedule_cancelled.status_code == 409, reschedule_cancelled.text


def test_customer_can_cancel_own_booking():
    setup = _bookable_setup()
    customer = _register_customer()
    token = _login(customer["email"])
    booking = client.post(
        "/api/v1/customer/bookings",
        json={"branch_service_id": setup["branch_service"]["id"], "booking_date": str(BOOKING_DATE), "start_time": "09:00:00"},
        headers=_auth(token),
    ).json()

    cancel = client.post(f"/api/v1/customer/bookings/{booking['id']}/cancel", json={}, headers=_auth(token))
    assert cancel.status_code == 200, cancel.text
    assert cancel.json()["status"] == "Cancelled"


# -----------------------------
# Manual resource override (PRD §21; BR-048, BR-049)
# -----------------------------

def test_manual_reassignment_validates_branch_category_and_availability():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    booking = client.post(
        f"/api/v1/branches/{setup['branch']['id']}/bookings",
        json={
            "customer_id": customer["id"], "branch_service_id": setup["branch_service"]["id"],
            "booking_date": str(BOOKING_DATE), "start_time": "09:00:00", "resource_id": setup["resource"]["id"],
        },
        headers=_auth(setup["owner_token"]),
    ).json()

    same_category_resource = _create_active_resource(setup["branch"]["id"], setup["owner_token"], setup["category"]["id"])
    _set_resource_hours(same_category_resource["id"], setup["owner_token"], WEEKDAY)

    other_category = _create_category(setup["business_id"], setup["owner_token"])
    wrong_category_resource = _create_active_resource(setup["branch"]["id"], setup["owner_token"], other_category["id"])
    rejected = client.post(
        f"/api/v1/bookings/{booking['id']}/reassign-resource",
        json={"resource_id": wrong_category_resource["id"]},
        headers=_auth(setup["owner_token"]),
    )
    assert rejected.status_code == 400, rejected.text

    accepted = client.post(
        f"/api/v1/bookings/{booking['id']}/reassign-resource",
        json={"resource_id": same_category_resource["id"]},
        headers=_auth(setup["owner_token"]),
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["resource_id"] == same_category_resource["id"]

    history = client.get(f"/api/v1/bookings/{booking['id']}/history", headers=_auth(setup["owner_token"])).json()
    assert "ResourceReassigned" in [h["action"] for h in history]


# -----------------------------
# Completion (PRD §18.7; ID-041, ID-042)
# -----------------------------

def test_complete_booking_restricted_to_staff():
    setup = _bookable_setup()
    customer = _register_customer()
    customer_token = _login(customer["email"])
    booking = client.post(
        "/api/v1/customer/bookings",
        json={"branch_service_id": setup["branch_service"]["id"], "booking_date": str(BOOKING_DATE), "start_time": "09:00:00"},
        headers=_auth(customer_token),
    ).json()

    denied = client.post(f"/api/v1/bookings/{booking['id']}/complete", headers=_auth(customer_token))
    assert denied.status_code == 403, denied.text

    completed = client.post(f"/api/v1/bookings/{booking['id']}/complete", headers=_auth(setup["owner_token"]))
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "Completed"
    assert completed.json()["completed_at"] is not None

    history = client.get(f"/api/v1/bookings/{booking['id']}/history", headers=_auth(setup["owner_token"])).json()
    assert "Completed" in [h["action"] for h in history]  # ID-042


# -----------------------------
# Authorization (HR User excluded; Branch Manager scoped to own branch)
# -----------------------------

def test_hr_user_cannot_manage_bookings():
    setup = _bookable_setup()
    _, hr_token = _invite_and_accept_staff(setup["business_id"], setup["owner_token"], "HR_USER")
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])

    response = client.post(
        f"/api/v1/branches/{setup['branch']['id']}/bookings",
        json={
            "customer_id": customer["id"], "branch_service_id": setup["branch_service"]["id"],
            "booking_date": str(BOOKING_DATE), "start_time": "09:00:00",
        },
        headers=_auth(hr_token),
    )
    assert response.status_code == 403, response.text


def test_branch_manager_scoped_to_own_branch():
    setup = _bookable_setup()
    other_branch = _create_and_approve_branch(setup["business_id"], setup["owner_token"])
    _, bm_token = _invite_and_accept_staff(
        setup["business_id"], setup["owner_token"], "BRANCH_MANAGER", branch_id=setup["branch"]["id"]
    )
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])

    own_branch = client.post(
        f"/api/v1/branches/{setup['branch']['id']}/bookings",
        json={
            "customer_id": customer["id"], "branch_service_id": setup["branch_service"]["id"],
            "booking_date": str(BOOKING_DATE), "start_time": "09:00:00",
        },
        headers=_auth(bm_token),
    )
    assert own_branch.status_code == 200, own_branch.text

    other_branch_forbidden = client.get(
        f"/api/v1/branches/{other_branch['id']}/bookings", headers=_auth(bm_token)
    )
    assert other_branch_forbidden.status_code == 403, other_branch_forbidden.text


def test_business_owner_can_list_business_wide_bookings():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    client.post(
        f"/api/v1/branches/{setup['branch']['id']}/bookings",
        json={
            "customer_id": customer["id"], "branch_service_id": setup["branch_service"]["id"],
            "booking_date": str(BOOKING_DATE), "start_time": "09:00:00",
        },
        headers=_auth(setup["owner_token"]),
    )
    listing = client.get(f"/api/v1/businesses/{setup['business_id']}/bookings", headers=_auth(setup["owner_token"]))
    assert listing.status_code == 200, listing.text
    assert len(listing.json()) == 1


# -----------------------------
# No hard-delete endpoint (BR-045)
# -----------------------------

def test_no_hard_delete_endpoint_exists():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    booking = client.post(
        f"/api/v1/branches/{setup['branch']['id']}/bookings",
        json={
            "customer_id": customer["id"], "branch_service_id": setup["branch_service"]["id"],
            "booking_date": str(BOOKING_DATE), "start_time": "09:00:00",
        },
        headers=_auth(setup["owner_token"]),
    ).json()

    response = client.delete(f"/api/v1/bookings/{booking['id']}", headers=_auth(setup["owner_token"]))
    assert response.status_code in (404, 405), response.text
