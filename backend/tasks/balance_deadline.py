"""
Milestone 8 Phase 7 — 48-hour balance deadline enforcement (ID-048/ID-049).

The platform's first automatic, system-triggered Booking lifecycle
transition. Each candidate row is processed through
`crud_payment.enforce_balance_deadline`, which re-locks and re-checks
before acting — see that function's docstring for the concurrency
guarantee against a simultaneous late payment.
"""
from celery_app import celery_app
from database import SessionLocal
from models import Booking
import crud_payment
import crud_booking
from services import notification_service, email_service


@celery_app.task(name="tasks.balance_deadline.enforce_balance_deadlines")
def enforce_balance_deadlines() -> int:
    db = SessionLocal()
    try:
        candidates = crud_payment.find_bookings_past_balance_deadline(db)
        cancelled = 0
        for financial in candidates:
            booking = db.query(Booking).filter(Booking.id == financial.booking_id).first()
            context = crud_booking.get_booking_notification_context(db, booking) if booking else None

            if crud_payment.enforce_balance_deadline(db, financial.id):
                cancelled += 1
                if booking and context:
                    notification_service.log_and_send(
                        booking.created_by, "BalanceDefaultCancellation",
                        lambda ctx=context: email_service.send_balance_default_cancellation_email(
                            ctx["email"], ctx["business_name"], ctx["branch_name"], ctx["service_name"],
                            ctx["booking_date"], ctx["start_time"],
                        ),
                        booking.business_id, "Booking", booking.id,
                    )
        return cancelled
    finally:
        db.close()
