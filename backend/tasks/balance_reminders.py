"""
Milestone 8 Phase 7 — 72-hour balance reminder (rule 6; ID-049).

Per ID-049, the database remains authoritative: this task re-reads current
state on every run and only acts on rows it currently finds due — nothing
is cached or assumed from a prior run. Idempotent via
`balance_reminder_sent_at`: a row is only ever matched once.
"""
from celery_app import celery_app
from database import SessionLocal
from models import Booking
import crud_payment
import crud_booking
from services import notification_service, email_service


@celery_app.task(name="tasks.balance_reminders.send_due_balance_reminders")
def send_due_balance_reminders() -> int:
    db = SessionLocal()
    try:
        due = crud_payment.find_bookings_due_for_balance_reminder(db)
        for financial in due:
            booking = db.query(Booking).filter(Booking.id == financial.booking_id).first()
            if not booking:
                continue
            context = crud_booking.get_booking_notification_context(db, booking)

            notification_service.log_and_send(
                booking.created_by, "BalanceReminder",
                lambda ctx=context, f=financial: email_service.send_balance_reminder_email(
                    ctx["email"], ctx["business_name"], ctx["branch_name"], ctx["service_name"],
                    ctx["booking_date"], ctx["start_time"], f.balance_due, f.balance_due_at,
                ),
                booking.business_id, "Booking", booking.id,
            )
            crud_payment.mark_balance_reminder_sent(db, financial)
        return len(due)
    finally:
        db.close()
