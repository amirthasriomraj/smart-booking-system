"""add payment and razorpay webhook event

Revision ID: d672bb7c0592
Revises: 59d14c6b7ce1
Create Date: 2026-09-03 13:56:39.000000

Milestone 8 — ID-046, ID-051, ID-052, ID-053, ID-055, ID-056.

Creates `payments` (a single payment collection attempt/transaction — see
`models.Payment`) and `razorpay_webhook_events` (raw webhook delivery log
and idempotency anchor, keyed by Razorpay's own event id — see
`models.RazorpayWebhookEvent`). No checkout signature is persisted
anywhere (`verified_at` replaces it) per rule 26.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd672bb7c0592'
down_revision: Union[str, Sequence[str], None] = '59d14c6b7ce1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("business_id", sa.Integer(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id", ondelete="CASCADE"), nullable=True),
        sa.Column("booking_hold_id", sa.Integer(), sa.ForeignKey("booking_holds.id"), nullable=True),
        sa.Column("payment_type", sa.String(), nullable=False),
        sa.Column("method", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="Created"),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(), nullable=False, server_default="INR"),
        sa.Column("razorpay_order_id", sa.String(), nullable=True),
        sa.Column("razorpay_payment_id", sa.String(), nullable=True),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("cash_received", sa.Numeric(10, 2), nullable=True),
        sa.Column("change_returned", sa.Numeric(10, 2), nullable=True),
        sa.Column("verified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("platform_fee_rate_snapshot", sa.Numeric(5, 2), nullable=True),
        sa.Column("platform_fee_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("gateway_fee_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("gateway_fee_tax_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(op.f("ix_payments_business_id"), "payments", ["business_id"])
    op.create_index(op.f("ix_payments_branch_id"), "payments", ["branch_id"])
    op.create_index(op.f("ix_payments_booking_id"), "payments", ["booking_id"])
    op.create_index(op.f("ix_payments_booking_hold_id"), "payments", ["booking_hold_id"])
    op.create_index(op.f("ix_payments_payment_type"), "payments", ["payment_type"])
    op.create_index(op.f("ix_payments_method"), "payments", ["method"])
    op.create_index(op.f("ix_payments_status"), "payments", ["status"])
    op.create_index(op.f("ix_payments_razorpay_order_id"), "payments", ["razorpay_order_id"])
    op.create_index(op.f("ix_payments_razorpay_payment_id"), "payments", ["razorpay_payment_id"])

    op.create_table(
        "razorpay_webhook_events",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("provider_event_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=False,
        ),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("processing_status", sa.String(), nullable=False, server_default="Received"),
        sa.UniqueConstraint("provider_event_id", name="uq_razorpay_webhook_events_provider_event_id"),
    )
    op.create_index(
        op.f("ix_razorpay_webhook_events_provider_event_id"), "razorpay_webhook_events", ["provider_event_id"]
    )
    op.create_index(op.f("ix_razorpay_webhook_events_event_type"), "razorpay_webhook_events", ["event_type"])
    op.create_index(
        op.f("ix_razorpay_webhook_events_processing_status"), "razorpay_webhook_events", ["processing_status"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("razorpay_webhook_events")
    op.drop_table("payments")
