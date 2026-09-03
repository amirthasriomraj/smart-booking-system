"""
Milestone 8 — Notification/EmailLog persistence (ID-050).

TAS Part 3 §10 specifies `Notifications`/`Email Logs` tables that were
never implemented through M7; M8 builds the persistence now because it
needs an auditable record of financial-lifecycle notifications (e.g.
"balance reminder sent" — rule 27). This wrapper opens its own DB session
so it is safe to call either from a FastAPI `BackgroundTasks` callback
(after the request's own session has closed) or directly from a Celery
task (which has no request-scoped session at all).

Matches PRD §37's "notification failures must never interrupt business
operations" principle already followed by the plain `email_service.py`
functions: any exception from the actual send is caught and recorded as a
Failed `Notification`/`EmailLog`, never re-raised.
"""
from datetime import datetime

from database import SessionLocal
from models import Notification, EmailLog


def log_and_send(
    recipient_user_id: int,
    notification_type: str,
    send_fn,
    business_id: int = None,
    related_entity_type: str = None,
    related_entity_id: int = None,
) -> None:
    db = SessionLocal()
    try:
        notification = Notification(
            business_id=business_id, recipient_user_id=recipient_user_id, notification_type=notification_type,
            channel="Email", status="Pending", related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
        )
        db.add(notification)
        db.flush()

        try:
            send_fn()
            notification.status = "Sent"
            notification.sent_at = datetime.utcnow()
            db.add(EmailLog(notification_id=notification.id, delivery_status="Sent"))
        except Exception as exc:
            notification.status = "Failed"
            db.add(EmailLog(notification_id=notification.id, delivery_status="Failed", provider_reference=str(exc)[:250]))

        db.commit()
    finally:
        db.close()
