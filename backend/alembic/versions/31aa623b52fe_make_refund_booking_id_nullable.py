"""make refund booking id nullable

Revision ID: 31aa623b52fe
Revises: 84ce37743b53
Create Date: 2026-09-03 16:11:27.246174

Milestone 8 Phase 5-7 — ID-056.

`refunds.booking_id` was originally NOT NULL (every refund assumed a real
Booking). The payment-succeeds-after-hold-expiry exceptional path
(decision 16) captures money against a `BookingHold` that never became a
`Booking` — the automatic refund issued for that captured payment has no
booking to reference. Relaxing to nullable is additive/backward-compatible:
every existing row already has a non-NULL booking_id, so no data is
affected.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '31aa623b52fe'
down_revision: Union[str, Sequence[str], None] = '84ce37743b53'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("refunds", "booking_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column("refunds", "booking_id", existing_type=sa.Integer(), nullable=False)
