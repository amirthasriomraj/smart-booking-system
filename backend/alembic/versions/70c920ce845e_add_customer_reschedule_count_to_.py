"""add customer_reschedule_count to bookings

Revision ID: 70c920ce845e
Revises: fd3dc88e01f6
Create Date: 2026-09-03 18:00:00.000000

Milestone 8 Phase 8 — ID-047.

Additive/backward-compatible: every existing Booking row gets
customer_reschedule_count=0 (server_default), preserving M7 behavior for
bookings that predate this milestone.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '70c920ce845e'
down_revision: Union[str, Sequence[str], None] = 'fd3dc88e01f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "bookings",
        sa.Column("customer_reschedule_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("bookings", "customer_reschedule_count")
