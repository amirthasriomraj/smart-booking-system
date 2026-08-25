"""add resource management

Revision ID: 9d3465940d54
Revises: 7f4c06f46451
Create Date: 2026-08-24 00:00:00.000000

Adds the Milestone 4 (Resource Management) schema (TAS Part 3 §7;
PRD §14.1-14.6), plus the Milestone 3 business_members column it stages
invitation state on (ID-014):

- resource_categories: business-scoped Resource Category (PRD §14.2).
- resources: generic Resource model (PRD §14.1/§14.3-14.5). Carries an
  explicit business_id, denormalized from branch.business_id at creation
  (ID-012 — the TAS §7 Resources column list omits it, but the TAS's
  "Entities requiring business_id" list names both Resource and Resource
  Category). Also carries max_bookings_per_day / booking_buffer_minutes,
  V1-mandatory attributes (PRD §14.3) the TAS schema has no columns for
  (ID-013 — storage only in Milestone 4, enforced in Milestone 7).
- resource_working_hours: per-weekday Resource hours, plus break_start_time /
  break_end_time (ID-013, same storage-only rationale).
- business_members.linked_resource_id: stages which Resource a pending
  Resource User invitation belongs to, mirroring invited_branch_id (ID-014).

Purely additive: no existing column is altered, no data is migrated.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9d3465940d54'
down_revision: Union[str, Sequence[str], None] = '7f4c06f46451'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "resource_categories",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("business_id", sa.Integer(), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        op.f("ix_resource_categories_business_id"), "resource_categories", ["business_id"], unique=False
    )

    op.create_table(
        "resources",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("business_id", sa.Integer(), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resource_category_id", sa.Integer(), sa.ForeignKey("resource_categories.id"), nullable=False),
        sa.Column("linked_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resource_name", sa.String(), nullable=False),
        sa.Column("code", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="Pending"),
        sa.Column("requires_login", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("max_bookings_per_day", sa.Integer(), nullable=True),
        sa.Column("booking_buffer_minutes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(op.f("ix_resources_branch_id"), "resources", ["branch_id"], unique=False)
    op.create_index(op.f("ix_resources_business_id"), "resources", ["business_id"], unique=False)
    op.create_index(op.f("ix_resources_resource_category_id"), "resources", ["resource_category_id"], unique=False)
    op.create_index(op.f("ix_resources_status"), "resources", ["status"], unique=False)

    op.create_table(
        "resource_working_hours",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("resource_id", sa.Integer(), sa.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("opening_time", sa.Time(), nullable=True),
        sa.Column("closing_time", sa.Time(), nullable=True),
        sa.Column("is_closed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("break_start_time", sa.Time(), nullable=True),
        sa.Column("break_end_time", sa.Time(), nullable=True),
        sa.UniqueConstraint("resource_id", "weekday", name="uq_resource_working_hours_resource_weekday"),
    )
    op.create_index(
        op.f("ix_resource_working_hours_resource_id"), "resource_working_hours", ["resource_id"], unique=False
    )

    op.add_column(
        "business_members",
        sa.Column("linked_resource_id", sa.Integer(), sa.ForeignKey("resources.id"), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("business_members", "linked_resource_id")

    op.drop_index(op.f("ix_resource_working_hours_resource_id"), table_name="resource_working_hours")
    op.drop_table("resource_working_hours")

    op.drop_index(op.f("ix_resources_status"), table_name="resources")
    op.drop_index(op.f("ix_resources_resource_category_id"), table_name="resources")
    op.drop_index(op.f("ix_resources_business_id"), table_name="resources")
    op.drop_index(op.f("ix_resources_branch_id"), table_name="resources")
    op.drop_table("resources")

    op.drop_index(op.f("ix_resource_categories_business_id"), table_name="resource_categories")
    op.drop_table("resource_categories")
