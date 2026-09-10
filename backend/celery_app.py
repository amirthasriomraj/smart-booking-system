"""
Celery application foundation (Milestone 8 — ID-049), with the Phase 7
scheduled business-flow tasks registered:

- `tasks.balance_reminders.send_due_balance_reminders` — rule 6's 72-hour
  reminder.
- `tasks.balance_deadline.enforce_balance_deadlines` — rule 6/ID-048's
  48-hour automatic cancellation/deposit forfeiture.
- `tasks.hold_expiry.sweep_expired_holds` — periodic status-accuracy
  cleanup only; not required for correctness (see that task's docstring).

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
    include=["tasks.health", "tasks.balance_reminders", "tasks.balance_deadline", "tasks.hold_expiry"],
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
    beat_schedule={
        # Reminder/deadline windows are hour-granularity (rule 6); a
        # 5-minute cadence keeps both comfortably inside their windows
        # without excessive polling. Hold expiry runs a bit more often
        # since holds only last 6-10 minutes.
        "send-due-balance-reminders": {
            "task": "tasks.balance_reminders.send_due_balance_reminders",
            "schedule": 300.0,
        },
        "enforce-balance-deadlines": {
            "task": "tasks.balance_deadline.enforce_balance_deadlines",
            "schedule": 300.0,
        },
        "sweep-expired-holds": {
            "task": "tasks.hold_expiry.sweep_expired_holds",
            "schedule": 60.0,
        },
    },
)
