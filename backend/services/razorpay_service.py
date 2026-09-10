"""
Milestone 8 Phase 4 — Razorpay Integration Boundary (ID-055).

Thin wrapper around the official `razorpay` Python SDK. Verified against
current Razorpay documentation and the installed SDK source
(razorpay==2.0.1) during Phase 4:

- Orders: `client.order.create({"amount": <paise>, "currency": ..., "receipt": ...})`.
  Amount is in the smallest currency unit (paise for INR) — every function
  here takes rupees as a `Decimal` and converts.
- Payment signature verification: `client.utility.verify_payment_signature`
  computes HMAC-SHA256 of `"{order_id}|{payment_id}"` using the key
  secret and raises `razorpay.errors.SignatureVerificationError` on
  mismatch (it never returns `False` — mismatch is always an exception).
- Webhook signature verification: `client.utility.verify_webhook_signature`
  computes HMAC-SHA256 of the *raw* request body using the separate
  webhook secret, transmitted via the `X-Razorpay-Signature` header. Per
  the official docs, the raw body must be passed unparsed/unmodified.
- Webhook idempotency: Razorpay's own recommendation is to key on the
  `x-razorpay-event-id` header (unique per delivery attempt is NOT
  guaranteed — redeliveries reuse the same event id) rather than anything
  derived from the payload — see `routers/payments_webhook.py`.
- Refunds: `client.payment.refund(payment_id, {"amount": <paise>})`.
- Payment fetch: `client.payment.fetch(payment_id)` — a server-to-server
  GET against Razorpay's Payments API returning the payment's current
  `status`/`amount`/etc. Milestone 8 Phase 8 explicit requirement: a valid
  checkout signature proves the `(order_id, payment_id)` pairing is
  authentic, but is NOT by itself proof that money was captured (a
  signature can be produced for an authorized-but-not-yet-captured, or
  even a since-refunded, payment). `fetch_payment` is used to confirm
  `status == "captured"` (and the amount matches) server-side before any
  Payment row is marked Captured — see `crud_payment._verify_and_capture_payment`.

Per ID-055, production Razorpay Route/Linked-Account activation is a
separate deployment/onboarding prerequisite and is not exercised by this
module — nothing here assumes Route is available. `RAZORPAY_MODE` ("test"
by default, see `config.py`) is informational only; it does not change
which API is called, only which credential pair is expected to be
configured.
"""
import razorpay
from decimal import Decimal, ROUND_HALF_UP

from config import get_settings

RUPEES_TO_PAISE = Decimal("100")


def _client() -> razorpay.Client:
    settings = get_settings()
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


def _to_paise(amount_rupees: Decimal) -> int:
    return int((Decimal(amount_rupees) * RUPEES_TO_PAISE).to_integral_value(rounding=ROUND_HALF_UP))


def to_paise(amount_rupees: Decimal) -> int:
    """Public alias of `_to_paise`, for callers (e.g. crud_payment.py) that
    need to compare a captured amount reported in paise against ours."""
    return _to_paise(amount_rupees)


def create_order(amount_rupees: Decimal, currency: str, receipt: str) -> dict:
    """Creates a Razorpay Order for a checkout attempt. `receipt` should be
    a caller-chosen identifier (e.g. the BookingHold id) for reconciliation
    — Razorpay does not enforce uniqueness on it."""
    client = _client()
    return client.order.create({
        "amount": _to_paise(amount_rupees),
        "currency": currency,
        "receipt": receipt,
    })


def create_payment_link(
    amount_rupees: Decimal,
    currency: str,
    description: str,
    customer_name: str,
    customer_email: str,
    customer_contact: str = None,
) -> dict:
    """For the staff-emailed-payment-link flow (business rule 12.B) — built
    now as part of the integration boundary; not wired to any endpoint
    until the Phase 6 staff checkout flows exist."""
    client = _client()
    customer = {"name": customer_name, "email": customer_email}
    if customer_contact:
        customer["contact"] = customer_contact
    return client.payment_link.create({
        "amount": _to_paise(amount_rupees),
        "currency": currency,
        "description": description,
        "customer": customer,
        "notify": {"sms": bool(customer_contact), "email": True},
    })


def verify_payment_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """Server-side proof that a checkout success callback is authentic
    (rule 11/26) — the frontend callback alone is never trusted. Returns
    False on any verification failure rather than letting
    SignatureVerificationError propagate, so callers can respond with a
    clean rejection."""
    client = _client()
    try:
        client.utility.verify_payment_signature({
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature,
        })
        return True
    except razorpay.errors.SignatureVerificationError:
        return False


def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
    """`raw_body` must be the exact, unparsed request body bytes (per
    Razorpay's documented requirement) — decoded to str here only because
    the SDK's HMAC implementation requires a str, not because the body is
    ever re-serialized from parsed JSON."""
    settings = get_settings()
    client = _client()
    body_str = raw_body.decode("utf-8") if isinstance(raw_body, (bytes, bytearray)) else raw_body
    try:
        client.utility.verify_webhook_signature(body_str, signature, settings.RAZORPAY_WEBHOOK_SECRET)
        return True
    except razorpay.errors.SignatureVerificationError:
        return False


def fetch_payment(payment_id: str) -> dict:
    """Server-to-server confirmation of a payment's actual state — see the
    module docstring. Never trust a signature alone as capture proof;
    callers must check the returned `status` (and `amount`) themselves."""
    client = _client()
    return client.payment.fetch(payment_id)


def create_refund(payment_id: str, amount_rupees: Decimal) -> dict:
    client = _client()
    return client.payment.refund(payment_id, {"amount": _to_paise(amount_rupees)})
