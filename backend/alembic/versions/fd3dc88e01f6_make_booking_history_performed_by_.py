"""make booking history performed_by nullable

Revision ID: fd3dc88e01f6
Revises: 31aa623b52fe
Create Date: 2026-09-03 16:20:00.000000

Milestone 8 Phase 5-7 — ID-048.

`booking_history.performed_by` was NOT NULL (every prior action always had
a human actor). The automatic 48-hour balance-default cancellation is the
platform's first system-triggered lifecycle transition and has no user to
attribute it to; NULL represents the system actor, mirroring the already-
nullable `audit_logs.performed_by`. Additive/backward-compatible: every
existing row already has a non-NULL performed_by.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fd3dc88e01f6'
down_revision: Union[str, Sequence[str], None] = '31aa623b52fe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("booking_history", "performed_by", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column("booking_history", "performed_by", existing_type=sa.Integer(), nullable=False)
