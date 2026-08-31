"""add customer management

Revision ID: 302fd62fdba4
Revises: aef8c25c0cec
Create Date: 2026-08-31 00:00:00.000000

Adds the Milestone 6 (Customer Management & Customer Portal) schema
(TAS Part 3 §6; PRD §17.1-17.6):

- platform_customers: the customer's platform identity, 1:1 with `users`
  (ID-028 — TAS §6's PlatformCustomer/BusinessCustomer split, adopted as
  authoritative over PRD §10.6/§11's contradictory "isolated per business"
  language).
- business_customers: the relationship between a platform customer and a
  specific business. `platform_customer_id` is NOT NULL — every Customer,
  including staff-created walk-ins, always has a backing platform identity
  (ID-030). `customer_number` is system-generated
  (`CUST-{business_customer.id:06d}`, ID-033); `UniqueConstraint` on both
  (business_id, platform_customer_id) and (business_id, customer_number) is
  a DB-level safety net (ID-031, ID-033).
- user_profiles gains new nullable columns (gender, date_of_birth,
  address_line, city, state, country_id, postal_code) to hold PRD §17.2's
  Personal/Contact/Address Information fields, which have no home anywhere
  in the TAS §6 schema (ID-029). Reuses the existing 1:1 profile table
  rather than duplicating first_name/last_name on PlatformCustomer.

No role is seeded here — CUSTOMER was already seeded by the Milestone 1
migration's ROLES list (915a434bff35_add_tenant_foundation_rbac_business_.py).

Purely additive: no existing column is altered or dropped, no data is
migrated.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '302fd62fdba4'
down_revision: Union[str, Sequence[str], None] = 'aef8c25c0cec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "platform_customers",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("preferred_language", sa.String(), nullable=True),
        sa.Column("preferred_timezone", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_platform_customers_user_id"),
    )
    op.create_index(op.f("ix_platform_customers_user_id"), "platform_customers", ["user_id"])

    op.create_table(
        "business_customers",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("business_id", sa.Integer(), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "platform_customer_id",
            sa.Integer(),
            sa.ForeignKey("platform_customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("customer_number", sa.String(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="Active"),
        sa.Column("first_visit_at", sa.DateTime(), nullable=True),
        sa.Column("last_visit_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("business_id", "platform_customer_id", name="uq_business_customer_business_platform_customer"),
        sa.UniqueConstraint("business_id", "customer_number", name="uq_business_customer_business_customer_number"),
    )
    op.create_index(op.f("ix_business_customers_business_id"), "business_customers", ["business_id"])
    op.create_index(op.f("ix_business_customers_platform_customer_id"), "business_customers", ["platform_customer_id"])
    op.create_index(op.f("ix_business_customers_status"), "business_customers", ["status"])

    op.add_column("user_profiles", sa.Column("gender", sa.String(), nullable=True))
    op.add_column("user_profiles", sa.Column("date_of_birth", sa.Date(), nullable=True))
    op.add_column("user_profiles", sa.Column("address_line", sa.String(), nullable=True))
    op.add_column("user_profiles", sa.Column("city", sa.String(), nullable=True))
    op.add_column("user_profiles", sa.Column("state", sa.String(), nullable=True))
    op.add_column("user_profiles", sa.Column("country_id", sa.Integer(), sa.ForeignKey("countries.id"), nullable=True))
    op.add_column("user_profiles", sa.Column("postal_code", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("user_profiles", "postal_code")
    op.drop_column("user_profiles", "country_id")
    op.drop_column("user_profiles", "state")
    op.drop_column("user_profiles", "city")
    op.drop_column("user_profiles", "address_line")
    op.drop_column("user_profiles", "date_of_birth")
    op.drop_column("user_profiles", "gender")

    op.drop_table("business_customers")
    op.drop_table("platform_customers")
