"""
Infrastructure smoke-test task only (Phase 0). Not part of any M8 business
flow — used to verify the Celery worker/beat/Redis wiring end-to-end before
real scheduled tasks are added in later M8 phases.
"""

from celery_app import celery_app


@celery_app.task(name="tasks.health.ping")
def ping() -> str:
    return "pong"
