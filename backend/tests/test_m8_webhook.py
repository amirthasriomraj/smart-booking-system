"""
Milestone 8 Phase 4 — Razorpay webhook endpoint tests.

Signature verification itself (services/razorpay_service.verify_webhook_signature)
is exercised directly with a real HMAC computed the same way Razorpay does
(HMAC-SHA256 of the raw body, hex digest), rather than mocking the SDK —
this proves the actual verification logic, not just that some function was
called.
"""
import hashlib
import hmac
import json

from config import get_settings
from database import SessionLocal
from models import RazorpayWebhookEvent
from tests.test_bookings import client  # noqa: F401 (shared TestClient)


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _webhook_secret() -> str:
    return get_settings().RAZORPAY_WEBHOOK_SECRET or "test-webhook-secret"


def setup_module(module):
    # Tests need a known, non-empty webhook secret regardless of what (if
    # anything) is configured for the running process — never read/print
    # the real .env value; this only ever sets an in-memory test secret.
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


def test_webhook_rejects_invalid_signature():
    body = json.dumps({"event": "payment.captured", "payload": {}}).encode()
    response = client.post(
        "/api/v1/webhooks/razorpay",
        content=body,
        headers={"X-Razorpay-Signature": "not-a-real-signature", "X-Razorpay-Event-Id": "evt_bad_sig"},
    )
    assert response.status_code == 400, response.text


def test_webhook_rejects_missing_event_id():
    body = json.dumps({"event": "payment.captured"}).encode()
    signature = _sign(body, _webhook_secret())
    response = client.post(
        "/api/v1/webhooks/razorpay",
        content=body,
        headers={"X-Razorpay-Signature": signature},
    )
    assert response.status_code == 400, response.text


def test_webhook_accepts_valid_signature_and_persists_event():
    body = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {"id": "pay_test123"}}}}).encode()
    signature = _sign(body, _webhook_secret())
    response = client.post(
        "/api/v1/webhooks/razorpay",
        content=body,
        headers={"X-Razorpay-Signature": signature, "X-Razorpay-Event-Id": "evt_accept_1"},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ok"}

    db = SessionLocal()
    try:
        stored = db.query(RazorpayWebhookEvent).filter(RazorpayWebhookEvent.provider_event_id == "evt_accept_1").first()
        assert stored is not None
        assert stored.event_type == "payment.captured"
        assert stored.processing_status == "Processed"
    finally:
        db.close()


def test_duplicate_webhook_delivery_is_idempotent():
    body = json.dumps({"event": "payment.captured"}).encode()
    signature = _sign(body, _webhook_secret())
    headers = {"X-Razorpay-Signature": signature, "X-Razorpay-Event-Id": "evt_dup_delivery"}

    first = client.post("/api/v1/webhooks/razorpay", content=body, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json().get("duplicate") is not True

    second = client.post("/api/v1/webhooks/razorpay", content=body, headers=headers)
    assert second.status_code == 200, second.text
    assert second.json().get("duplicate") is True

    db = SessionLocal()
    try:
        count = (
            db.query(RazorpayWebhookEvent)
            .filter(RazorpayWebhookEvent.provider_event_id == "evt_dup_delivery")
            .count()
        )
        assert count == 1  # never duplicated despite two deliveries
    finally:
        db.close()
