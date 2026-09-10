"""add refund

Revision ID: d9492e8901e0
Revises: d672bb7c0592
Create Date: 2026-09-03 13:56:43.000000

Milestone 8 — ID-053, ID-056, rule 16.

Creates `refunds`, the single authoritative record of money returned to a
customer (see `models.Refund`). `Payment.status` is never mutated to
represent a refund.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9492e8901e0'
down_revision: Union[str, Sequence[str], None] = 'd672bb7c0592'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "refunds",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("business_id", sa.Integer(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id"), nullable=False),
        sa.Column("calculated_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("overridden_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("final_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role_snapshot", sa.String(), nullable=False),
        sa.Column("refund_method", sa.String(), nullable=False),
        sa.Column("razorpay_refund_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="Initiated"),
        sa.Column("platform_fee_reversal_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index(op.f("ix_refunds_business_id"), "refunds", ["business_id"])
    op.create_index(op.f("ix_refunds_branch_id"), "refunds", ["branch_id"])
    op.create_index(op.f("ix_refunds_booking_id"), "refunds", ["booking_id"])
    op.create_index(op.f("ix_refunds_payment_id"), "refunds", ["payment_id"])
    op.create_index(op.f("ix_refunds_refund_method"), "refunds", ["refund_method"])
    op.create_index(op.f("ix_refunds_razorpay_refund_id"), "refunds", ["razorpay_refund_id"])
    op.create_index(op.f("ix_refunds_status"), "refunds", ["status"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("refunds")
