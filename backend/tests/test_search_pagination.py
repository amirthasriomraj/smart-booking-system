"""M9 Phase 5 — search/filter/pagination on the 6 canonical list endpoints
(Resources, Bookings, Services, Branches, Businesses business-wide; Customer
coverage lives in test_customers.py). Each test asserts the {items, total,
page, page_size, total_pages} envelope plus at least one search/filter
capability named in PRD §38-40."""

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
    admin_username = f"searchadmin_{unique}"
    _register_business(username=admin_username, email=f"{admin_username}@example.com")
    _promote_to_platform_admin(admin_username)
    admin_token = _login(admin_username)

    owner_username = f"searchowner_{unique}"
    reg = _register_business(username=owner_username, email=f"{owner_username}@example.com")
    business_id = reg.json()["id"]
    owner_token = _login(owner_username)

    approve = client.post(f"/api/v1/businesses/{business_id}/approve", headers=_auth(admin_token))
    assert approve.status_code == 200
    return business_id, owner_token, admin_token


def _create_branch(business_id, owner_token, branch_name=None, admin_token=None):
    payload = {"branch_name": branch_name or f"Branch {uuid.uuid4().hex[:8]}", "country_id": _country_id()}
    response = client.post(f"/api/v1/businesses/{business_id}/branches", json=payload, headers=_auth(owner_token))
    assert response.status_code == 200, response.text
    branch = response.json()
    if admin_token:
        approve = client.post(f"/api/v1/branches/{branch['id']}/approve", headers=_auth(admin_token))
        assert approve.status_code == 200
        activate = client.post(f"/api/v1/branches/{branch['id']}/activate", headers=_auth(owner_token))
        assert activate.status_code == 200
    return branch


# -----------------------------
# Branches
# -----------------------------

def test_branches_list_supports_search_and_pagination_envelope():
    business_id, owner_token, admin_token = _register_and_approve_business()
    unique = uuid.uuid4().hex[:8]
    _create_branch(business_id, owner_token, branch_name=f"Downtown {unique}")
    _create_branch(business_id, owner_token, branch_name=f"Uptown {unique}")

    response = client.get(f"/api/v1/businesses/{business_id}/branches", headers=_auth(owner_token))
    assert response.status_code == 200, response.text
    body = response.json()
    for key in ("items", "total", "page", "page_size", "total_pages"):
        assert key in body
    assert body["total"] == 2

    search = client.get(
        f"/api/v1/businesses/{business_id}/branches",
        params={"search": "Downtown"},
        headers=_auth(owner_token),
    )
    assert search.status_code == 200
    assert search.json()["total"] == 1
    assert "Downtown" in search.json()["items"][0]["branch_name"]


# -----------------------------
# Resources
# -----------------------------

def test_resources_list_supports_search_filter_and_pagination_envelope():
    business_id, owner_token, admin_token = _register_and_approve_business()
    branch = _create_branch(business_id, owner_token, admin_token=admin_token)
    unique = uuid.uuid4().hex[:8]

    category = client.post(
        f"/api/v1/businesses/{business_id}/resource-categories",
        json={"category_name": f"Category {unique}"},
        headers=_auth(owner_token),
    ).json()

    resource1 = client.post(
        f"/api/v1/branches/{branch['id']}/resources",
        json={
            "resource_category_id": category["id"],
            "resource_name": f"Searchable Resource {unique}",
            "requires_login": False,
        },
        headers=_auth(owner_token),
    ).json()
    client.post(
        f"/api/v1/branches/{branch['id']}/resources",
        json={
            "resource_category_id": category["id"],
            "resource_name": f"Other Resource {unique}",
            "requires_login": False,
        },
        headers=_auth(owner_token),
    )

    response = client.get(f"/api/v1/businesses/{business_id}/resources", headers=_auth(owner_token))
    assert response.status_code == 200, response.text
    body = response.json()
    for key in ("items", "total", "page", "page_size", "total_pages"):
        assert key in body
    assert body["total"] == 2

    search = client.get(
        f"/api/v1/businesses/{business_id}/resources",
        params={"search": "Searchable"},
        headers=_auth(owner_token),
    )
    assert search.status_code == 200
    assert search.json()["total"] == 1
    assert search.json()["items"][0]["id"] == resource1["id"]

    by_branch = client.get(
        f"/api/v1/businesses/{business_id}/resources",
        params={"branch_id": branch["id"]},
        headers=_auth(owner_token),
    )
    assert by_branch.status_code == 200
    assert by_branch.json()["total"] == 2


# -----------------------------
# Businesses (Platform Admin)
# -----------------------------

def test_businesses_list_supports_search_by_name():
    _, _, admin_token = _register_and_approve_business()
    unique = uuid.uuid4().hex[:8]
    reg = _register_business(business_name=f"UniqueSearchable Co {unique}")
    assert reg.status_code == 200

    response = client.get(
        "/api/v1/businesses/",
        params={"search": "UniqueSearchable"},
        headers=_auth(admin_token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    for key in ("items", "total", "page", "page_size", "total_pages"):
        assert key in body
    assert body["total"] == 1
    assert reg.json()["id"] == body["items"][0]["id"]


# -----------------------------
# Services (business-wide Branch Services)
# -----------------------------

def test_branch_services_list_supports_search_and_pagination_envelope():
    business_id, owner_token, admin_token = _register_and_approve_business()
    _create_branch(business_id, owner_token, admin_token=admin_token)
    unique = uuid.uuid4().hex[:8]

    template = client.post(
        f"/api/v1/businesses/{business_id}/service-templates",
        json={"name": f"Distinctive Service {unique}", "default_duration": 30, "default_price": "100.00"},
        headers=_auth(owner_token),
    )
    assert template.status_code == 200, template.text

    response = client.get(f"/api/v1/businesses/{business_id}/branch-services", headers=_auth(owner_token))
    assert response.status_code == 200, response.text
    body = response.json()
    for key in ("items", "total", "page", "page_size", "total_pages"):
        assert key in body
    assert body["total"] == 1

    search = client.get(
        f"/api/v1/businesses/{business_id}/branch-services",
        params={"search": "Distinctive"},
        headers=_auth(owner_token),
    )
    assert search.status_code == 200
    assert search.json()["total"] == 1

    no_match = client.get(
        f"/api/v1/businesses/{business_id}/branch-services",
        params={"search": "NoSuchServiceName"},
        headers=_auth(owner_token),
    )
    assert no_match.status_code == 200
    assert no_match.json()["total"] == 0


# -----------------------------
# Bookings (business-wide)
# -----------------------------

def _bookable_setup():
    business_id, owner_token, admin_token = _register_and_approve_business()
    branch = _create_branch(business_id, owner_token, admin_token=admin_token)
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
    hours_response = client.put(
        f"/api/v1/resources/{resource['id']}/working-hours",
        json={"hours": [{"weekday": BOOKING_DATE.weekday(), "opening_time": "09:00:00", "closing_time": "17:00:00"}]},
        headers=_auth(owner_token),
    )
    assert hours_response.status_code == 200, hours_response.text

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

    return business_id, owner_token, branch, resource, branch_service, walk_in


def test_bookings_list_supports_pagination_envelope_and_filters():
    business_id, owner_token, branch, resource, branch_service, customer = _bookable_setup()

    created = client.post(
        f"/api/v1/branches/{branch['id']}/bookings",
        json={
            "customer_id": customer["id"],
            "branch_service_id": branch_service["id"],
            "booking_date": str(BOOKING_DATE),
            "start_time": "09:00:00",
        },
        headers=_auth(owner_token),
    )
    assert created.status_code == 200, created.text
    booking = created.json()

    response = client.get(f"/api/v1/businesses/{business_id}/bookings", headers=_auth(owner_token))
    assert response.status_code == 200, response.text
    body = response.json()
    for key in ("items", "total", "page", "page_size", "total_pages"):
        assert key in body
    assert body["total"] == 1
    assert body["items"][0]["id"] == booking["id"]

    by_resource = client.get(
        f"/api/v1/businesses/{business_id}/bookings",
        params={"resource_id": resource["id"]},
        headers=_auth(owner_token),
    )
    assert by_resource.status_code == 200
    assert by_resource.json()["total"] == 1

    by_wrong_resource = client.get(
        f"/api/v1/businesses/{business_id}/bookings",
        params={"resource_id": resource["id"] + 999999},
        headers=_auth(owner_token),
    )
    assert by_wrong_resource.status_code == 200
    assert by_wrong_resource.json()["total"] == 0

    by_id_search = client.get(
        f"/api/v1/businesses/{business_id}/bookings",
        params={"search": str(booking["id"])},
        headers=_auth(owner_token),
    )
    assert by_id_search.status_code == 200
    assert by_id_search.json()["total"] == 1
