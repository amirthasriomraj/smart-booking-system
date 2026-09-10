"""
Regression tests for a finalization race diagnosed against a live Razorpay
Test Mode payment (hold 114): once the webhook was wired up, it and a
client-triggered finalization (customer `/verify`) could both call
`_finalize_hold_to_booking` for the same hold/payment. Whichever call lost
the race saw the hold already `Completed` (not `Active`) and — before the
fix — was treated as a genuinely lost/expired hold: it issued an automatic
Razorpay refund for a payment that had, in fact, already paid for a real
Confirmed booking, then returned 409 "This slot is no longer available."

The fix (`_finalize_hold_to_booking` in crud_payment.py) makes finalization
idempotent on `payment.booking_id`: whichever caller arrives second simply
returns the already-created booking instead of treating it as lost. These
tests cover both race directions and confirm no duplicate Booking/Payment
and no spurious Refund is ever created, while the genuine lost-hold refund
path (payment captured against a hold that never won any finalization,
covered by `test_payment_after_lost_hold_triggers_automatic_refund_not_double_booking`
in test_m8_checkout.py) is left unchanged.
"""
import hashlib
import hmac
import json

import pytest

from database import SessionLocal
from tests.test_bookings import (  # noqa: F401 (autouse fixtures)
    _bookable_setup,
    client,
    _auth,
    seed_reference_data,
    stub_booking_emails,
    BOOKING_DATE,
)
import crud_payment
from models import BookingHold, Payment, Booking, Refund, RazorpayWebhookEvent


@pytest.fixture(autouse=True)
def stub_razorpay(monkeypatch):
    calls = {"create_refund": 0}
    monkeypatch.setattr(
        crud_payment.razorpay_service, "create_order",
        lambda amount, currency, receipt: {"id": f"order_fake_{receipt}"},
    )
    monkeypatch.setattr(crud_payment.razorpay_service, "verify_payment_signature", lambda *a, **k: True)
    monkeypatch.setattr(crud_payment.razorpay_service, "fetch_payment", lambda payment_id: {"status": "captured", "amount": 10**12})
    monkeypatch.setattr(crud_payment.razorpay_service, "to_paise", lambda amount: 10**12)

    def _create_refund(*a, **k):
        calls["create_refund"] += 1
        return {"id": "rfnd_fake", "status": "processed"}

    monkeypatch.setattr(crud_payment.razorpay_service, "create_refund", _create_refund)
    return calls


def setup_module(module):
    # Same isolated, in-memory-only test secret pattern as test_m8_webhook.py
    # — never reads/prints the real .env value.
    import config
    config.get_settings.cache_clear()
    import os
    os.environ["RAZORPAY_WEBHOOK_SECRET"] = "test-webhook-secret"
    config.get_settings.cache_clear()


def teardown_module(module):
    import config
    import os
    os.environ.pop("RAZORPAY_WEBHOOK_SECRET", None)
    config.get_settings.cache_clear()


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _webhook_secret() -> str:
    from config import get_settings
    return get_settings().RAZORPAY_WEBHOOK_SECRET


def _customer_token_for(setup):
    import uuid
    unique = uuid.uuid4().hex[:8]
    payload = {
        "first_name": "Cust", "last_name": "Omer", "email": f"cust_{unique}@example.com",
        "mobile_number": "9999999999", "password": "Testpass123",
    }
    response = client.post("/api/v1/customers/register", json=payload)
    assert response.status_code == 200, response.text
    login = client.post("/api/v1/auth/login", data={"username": payload["email"], "password": "Testpass123"})
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def _start_checkout(setup, customer_token):
    checkout = client.post(
        "/api/v1/customer/checkout",
        json={
            "branch_service_id": setup["branch_service"]["id"], "booking_date": str(BOOKING_DATE),
            "start_time": "09:00:00", "payment_option": "Full",
        },
        headers=_auth(customer_token),
    )
    assert checkout.status_code == 200, checkout.text
    body = checkout.json()
    assert body["status"] == "AwaitingPayment"
    return body


def _post_payment_captured_webhook(order_id: str, razorpay_payment_id: str, event_id: str):
    body = json.dumps({
        "event": "payment.captured",
        "payload": {"payment": {"entity": {"id": razorpay_payment_id, "order_id": order_id}}},
    }).encode()
    signature = _sign(body, _webhook_secret())
    return client.post(
        "/api/v1/webhooks/razorpay",
        content=body,
        headers={"X-Razorpay-Signature": signature, "X-Razorpay-Event-Id": event_id},
    )


def test_webhook_wins_race_then_client_verify_is_idempotent_no_op(stub_razorpay):
    """Reproduces hold 114 exactly: the Razorpay webhook's `payment.captured`
    event finalizes the hold first; the customer's own browser callback to
    `/verify` arrives after. The second call must return the SAME booking
    (200), never a 409, and must never create a duplicate Booking or trigger
    a refund of the payment that already paid for a real booking."""
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    checkout = _start_checkout(setup, customer_token)
    hold_id = checkout["hold_id"]

    webhook_response = _post_payment_captured_webhook(
        checkout["razorpay_order_id"], "pay_fake_webhook_wins", "evt_webhook_wins_1",
    )
    assert webhook_response.status_code == 200, webhook_response.text

    db = SessionLocal()
    try:
        hold = db.query(BookingHold).filter(BookingHold.id == hold_id).first()
        assert hold.status == "Completed"
        payment = db.query(Payment).filter(Payment.booking_hold_id == hold_id).first()
        assert payment.status == "Captured"
        assert payment.booking_id is not None
        winning_booking_id = payment.booking_id
        assert db.query(Booking).filter(Booking.id == winning_booking_id).count() == 1
    finally:
        db.close()

    # The client's own /verify call arrives moments later, unaware the
    # webhook already finalized this hold.
    verify = client.post(
        f"/api/v1/customer/checkout/{hold_id}/verify",
        json={"razorpay_payment_id": "pay_fake_browser_callback", "razorpay_signature": "sig_fake_1"},
        headers=_auth(customer_token),
    )
    assert verify.status_code == 200, verify.text
    assert verify.json()["booking"]["id"] == winning_booking_id
    assert verify.json()["status"] == "Confirmed"

    db = SessionLocal()
    try:
        assert db.query(Booking).filter(Booking.id == winning_booking_id).count() == 1
        assert db.query(Payment).filter(Payment.booking_hold_id == hold_id).count() == 1  # no duplicate Payment
        assert db.query(Refund).filter(Refund.payment_id == payment.id).count() == 0  # never refunded
    finally:
        db.close()
    assert stub_razorpay["create_refund"] == 0


def test_client_verify_wins_race_then_late_webhook_is_a_safe_no_op(stub_razorpay):
    """The opposite direction: the customer's own /verify call finalizes
    first; the Razorpay webhook's payment.captured event for the same
    payment is delivered afterward (a genuinely new event id, not a
    redelivery of one already seen). The webhook must still return 200 and
    persist its own event row, but must not create a duplicate Booking or
    trigger any refund."""
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    checkout = _start_checkout(setup, customer_token)
    hold_id = checkout["hold_id"]

    verify = client.post(
        f"/api/v1/customer/checkout/{hold_id}/verify",
        json={"razorpay_payment_id": "pay_fake_verify_wins", "razorpay_signature": "sig_fake_1"},
        headers=_auth(customer_token),
    )
    assert verify.status_code == 200, verify.text
    winning_booking_id = verify.json()["booking"]["id"]

    webhook_response = _post_payment_captured_webhook(
        checkout["razorpay_order_id"], "pay_fake_verify_wins", "evt_client_wins_1",
    )
    assert webhook_response.status_code == 200, webhook_response.text
    assert webhook_response.json() == {"status": "ok"}  # accepted as a new event, not flagged duplicate

    db = SessionLocal()
    try:
        assert db.query(Booking).filter(Booking.id == winning_booking_id).count() == 1
        payment = db.query(Payment).filter(Payment.booking_hold_id == hold_id).first()
        assert payment.booking_id == winning_booking_id
        assert db.query(Payment).filter(Payment.booking_hold_id == hold_id).count() == 1
        assert db.query(Refund).filter(Refund.payment_id == payment.id).count() == 0

        event = db.query(RazorpayWebhookEvent).filter(RazorpayWebhookEvent.provider_event_id == "evt_client_wins_1").first()
        assert event is not None
        assert event.processing_status == "Processed"  # still recorded, just a no-op reconciliation
    finally:
        db.close()
    assert stub_razorpay["create_refund"] == 0
