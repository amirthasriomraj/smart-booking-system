"""
Milestone 8 Phase 4 — Razorpay webhook endpoint (ID-055/ID-056; rule 26).

This is the first unauthenticated (no JWT) route in the codebase — Razorpay
calls it directly, not a logged-in user — but every request is
cryptographically verified via HMAC signature before anything is trusted.

No M8 business-flow event processing is wired up yet (Phase 5+ adds actual
`payment.captured`/`refund.processed`/etc. handling once a checkout flow
exists to react to). This phase's scope is the verified, idempotent
*receipt* boundary: signature verification, raw-event persistence keyed by
Razorpay's own event id, and a clean 400 on an invalid signature.
"""
import json
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import SessionLocal
from models import RazorpayWebhookEvent
from services import razorpay_service

router = APIRouter(tags=["Payments Webhook"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/webhooks/razorpay")
async def razorpay_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_razorpay_signature: str = Header(default=None, alias="X-Razorpay-Signature"),
    x_razorpay_event_id: str = Header(default=None, alias="X-Razorpay-Event-Id"),
):
    # Raw, unparsed body — required by Razorpay's signature algorithm
    # (parsing/re-serializing before verification would invalidate it).
    raw_body = await request.body()

    if not x_razorpay_signature or not razorpay_service.verify_webhook_signature(raw_body, x_razorpay_signature):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    if not x_razorpay_event_id:
        raise HTTPException(status_code=400, detail="Missing X-Razorpay-Event-Id header")

    # Idempotency (ID-056): Razorpay may redeliver the same event id, and
    # events may arrive out of order — never reprocess an id already seen.
    existing = (
        db.query(RazorpayWebhookEvent)
        .filter(RazorpayWebhookEvent.provider_event_id == x_razorpay_event_id)
        .first()
    )
    if existing:
        return {"status": "ok", "duplicate": True}

    try:
        payload = json.loads(raw_body)
    except ValueError:
        payload = {}
    event_type = payload.get("event", "unknown")

    event = RazorpayWebhookEvent(
        provider_event_id=x_razorpay_event_id,
        event_type=event_type,
        payload=payload,
        processing_status="Received",
    )
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        # A concurrent delivery of the same event id won the race — its row
        # already satisfies idempotency, nothing left for this request to do.
        db.rollback()
        return {"status": "ok", "duplicate": True}

    event.processing_status = "Processed"
    event.processed_at = datetime.utcnow()
    db.commit()

    return {"status": "ok"}
