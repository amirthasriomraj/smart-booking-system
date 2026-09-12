"""
Tests for the small backend read/write surface added to support the M8
frontend: booking financial fields on BookingResponse, a booking
payment/refund history endpoint, and Platform Fee configuration for
Platform Admin. No new business logic — these only expose data the M8
payment engine already computes and persists.
"""
from decimal import Decimal

import pytest

from tests.test_bookings import (  # noqa: F401 (autouse fixtures)
    _bookable_setup,
    client,
    _auth,
    seed_reference_data,
    stub_booking_emails,
    BOOKING_DATE,
    _promote_to_platform_admin,
    _login,
    _register_business,
)
import crud_payment


def _customer_token_for(setup):
    import uuid
    unique = uuid.uuid4().hex[:8]
    payload = {
        "first_name": "Cust", "last_name": "Omer", "email": f"cust_{unique}@example.com",
        "mobile_number": "9999999999", "password": "Testpass123!",
    }
    response = client.post("/api/v1/customers/register", json=payload)
    assert response.status_code == 200, response.text
    login = client.post("/api/v1/auth/login", data={"username": payload["email"], "password": "Testpass123!"})
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


@pytest.fixture(autouse=True)
def stub_razorpay(monkeypatch):
    monkeypatch.setattr(
        crud_payment.razorpay_service, "create_order",
        lambda amount, currency, receipt: {"id": f"order_fake_{receipt}"},
    )
    monkeypatch.setattr(crud_payment.razorpay_service, "verify_payment_signature", lambda *a, **k: True)
    monkeypatch.setattr(crud_payment.razorpay_service, "fetch_payment", lambda payment_id: {"status": "captured", "amount": 10**12})
    monkeypatch.setattr(crud_payment.razorpay_service, "to_paise", lambda amount: 10**12)


def test_legacy_booking_has_no_financial_fields():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    checkout = client.post(
        "/api/v1/customer/bookings",
        json={
            "branch_service_id": setup["branch_service"]["id"], "booking_date": str(BOOKING_DATE),
            "start_time": "09:00:00",
        },
        headers=_auth(customer_token),
    )
    assert checkout.status_code == 200, checkout.text
    body = checkout.json()
    assert body["financial_status"] is None
    assert body["amount_paid"] is None


def test_full_payment_booking_exposes_financial_fields():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    checkout = client.post(
        "/api/v1/customer/checkout",
        json={
            "branch_service_id": setup["branch_service"]["id"], "booking_date": str(BOOKING_DATE),
            "start_time": "09:00:00", "payment_option": "Full",
        },
        headers=_auth(customer_token),
    ).json()
    verify = client.post(
        f"/api/v1/customer/checkout/{checkout['hold_id']}/verify",
        json={"razorpay_payment_id": "pay_hist_1", "razorpay_signature": "sig_hist_1"},
        headers=_auth(customer_token),
    ).json()
    booking = verify["booking"]
    assert booking["financial_status"] == "FullyPaid"
    assert Decimal(booking["amount_paid"]) == Decimal(booking["total_amount"])

    get_response = client.get(f"/api/v1/customer/bookings/{booking['id']}", headers=_auth(customer_token))
    assert get_response.json()["financial_status"] == "FullyPaid"


def test_payment_history_visible_to_owning_customer_and_staff():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    checkout = client.post(
        "/api/v1/customer/checkout",
        json={
            "branch_service_id": setup["branch_service"]["id"], "booking_date": str(BOOKING_DATE),
            "start_time": "09:00:00", "payment_option": "Full",
        },
        headers=_auth(customer_token),
    ).json()
    verify = client.post(
        f"/api/v1/customer/checkout/{checkout['hold_id']}/verify",
        json={"razorpay_payment_id": "pay_hist_2", "razorpay_signature": "sig_hist_2"},
        headers=_auth(customer_token),
    ).json()
    booking_id = verify["booking"]["id"]

    customer_view = client.get(f"/api/v1/customer/bookings/{booking_id}/payments", headers=_auth(customer_token))
    assert customer_view.status_code == 200, customer_view.text
    assert len(customer_view.json()["payments"]) == 1
    assert customer_view.json()["payments"][0]["status"] == "Captured"

    staff_view = client.get(f"/api/v1/bookings/{booking_id}/payments", headers=_auth(setup["owner_token"]))
    assert staff_view.status_code == 200, staff_view.text
    assert len(staff_view.json()["payments"]) == 1


def test_payment_history_rejects_non_owning_customer():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    other_customer_token = _customer_token_for(setup)
    checkout = client.post(
        "/api/v1/customer/checkout",
        json={
            "branch_service_id": setup["branch_service"]["id"], "booking_date": str(BOOKING_DATE),
            "start_time": "09:00:00", "payment_option": "Full",
        },
        headers=_auth(customer_token),
    ).json()
    verify = client.post(
        f"/api/v1/customer/checkout/{checkout['hold_id']}/verify",
        json={"razorpay_payment_id": "pay_hist_3", "razorpay_signature": "sig_hist_3"},
        headers=_auth(customer_token),
    ).json()
    booking_id = verify["booking"]["id"]

    response = client.get(f"/api/v1/customer/bookings/{booking_id}/payments", headers=_auth(other_customer_token))
    assert response.status_code == 403, response.text


def _platform_admin_token():
    import uuid
    unique = uuid.uuid4().hex[:8]
    admin_username = f"feeadmin_{unique}"
    _register_business(username=admin_username, email=f"{admin_username}@example.com")
    _promote_to_platform_admin(admin_username)
    return _login(admin_username)


def test_platform_fee_settings_default_and_override_roundtrip():
    admin_token = _platform_admin_token()
    setup = _bookable_setup()

    initial = client.get("/api/v1/platform-fee-settings", headers=_auth(admin_token))
    assert initial.status_code == 200, initial.text

    set_default = client.post(
        "/api/v1/platform-fee-settings/default",
        json={"fee_percentage": "2.50"},
        headers=_auth(admin_token),
    )
    assert set_default.status_code == 200, set_default.text
    assert Decimal(set_default.json()["default_fee_percentage"]) == Decimal("2.50")

    set_override = client.post(
        f"/api/v1/businesses/{setup['business_id']}/fee-override",
        json={"fee_percentage": "1.00", "reason": "Negotiated rate"},
        headers=_auth(admin_token),
    )
    assert set_override.status_code == 200, set_override.text
    overrides = set_override.json()["overrides"]
    assert any(o["business_id"] == setup["business_id"] and Decimal(o["fee_percentage"]) == Decimal("1.00") for o in overrides)

    remove_override = client.post(
        f"/api/v1/businesses/{setup['business_id']}/fee-override/remove",
        json={"reason": "Rate renegotiation ended"},
        headers=_auth(admin_token),
    )
    assert remove_override.status_code == 200, remove_override.text
    assert not any(o["business_id"] == setup["business_id"] for o in remove_override.json()["overrides"])


def test_platform_fee_override_requires_reason():
    admin_token = _platform_admin_token()
    setup = _bookable_setup()

    response = client.post(
        f"/api/v1/businesses/{setup['business_id']}/fee-override",
        json={"fee_percentage": "1.00"},
        headers=_auth(admin_token),
    )
    assert response.status_code == 422, response.text


def test_platform_fee_settings_rejected_for_non_admin():
    setup = _bookable_setup()
    response = client.get("/api/v1/platform-fee-settings", headers=_auth(setup["owner_token"]))
    assert response.status_code == 403, response.text
