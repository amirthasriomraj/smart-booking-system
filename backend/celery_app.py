"""
Celery application foundation (Milestone 8 — ID-049).

This is infrastructure only: no M8 business-flow tasks (balance reminders,
the 48-hour balance-deadline sweep, hold-expiry cleanup, etc.) are
registered yet — those are added in their respective M8 business-flow
phases. `tasks/health.py` provides one trivial task solely to verify the
worker/beat wiring end-to-end.

Per ID-049, the database remains authoritative: a scheduled task firing is
a trigger to re-read and validate current DB state, never a command to
blindly act, and every task must be safe to run more than once.
"""

from celery import Celery

from config import get_settings

settings = get_settings()

celery_app = Celery(
    "smart_booking_system",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["tasks.health"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Redelivery must be safe (ID-049/ID-056): tasks are idempotent, so
    # acknowledging only after completion (rather than on receipt) is safe
    # and avoids losing a task if a worker dies mid-run.
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # M8 business-flow phases (72h reminder, 48h sweep, hold-expiry cleanup)
    # register their schedules here; intentionally empty in Phase 0.
    beat_schedule={},
)
