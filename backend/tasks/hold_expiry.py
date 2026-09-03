"""
Milestone 8 Phase 7 — periodic hold-expiry sweep (ID-046/ID-049).

Not required for correctness (occupancy already excludes lapsed holds by
`expires_at` at read time, and `_expire_stale_holds_for_resource_date`
inline-expires stale rows before any new insert — see crud_booking.py).
This periodic sweep exists only to keep `BookingHold.status` accurate for
reporting/audit in the common case where no new hold happens to touch that
same resource/date afterward.
"""
from celery_app import celery_app
from database import SessionLocal
import crud_hold


@celery_app.task(name="tasks.hold_expiry.sweep_expired_holds")
def sweep_expired_holds() -> int:
    db = SessionLocal()
    try:
        return crud_hold.sweep_expired_holds(db)
    finally:
        db.close()
