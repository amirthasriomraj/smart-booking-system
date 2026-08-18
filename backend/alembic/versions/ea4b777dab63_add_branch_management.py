"""add branch management

Revision ID: ea4b777dab63
Revises: 915a434bff35
Create Date: 2026-08-18 12:55:53.879484

Adds the Milestone 2 Branch foundation (TAS Part 3 §4, §5; PRD §12 Step 5,
§13, BR-011-016):

- branches: Business Owner branch CRUD + Platform Admin approval. Status is
  split into approval_status (Platform Admin) and is_active (Business Owner)
  as an approved deviation from the TAS's single `status` column — see the
  Milestone 2 plan for why.
- branch_working_hours: per-weekday operating hours, one row per weekday.
- branch_assignments: Branch Manager transfer history (TAS Part 3 §5).
  Schema only in this milestone — no endpoint writes to it yet. A partial
  unique index enforces "only one current assignment per business_member"
  at the database level.

Purely additive: no existing table is modified.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ea4b777dab63'
down_revision: Union[str, Sequence[str], None] = '915a434bff35'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.create_table(
        "branches",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("business_id", sa.Integer(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("branch_name", sa.String(), nullable=False),
        sa.Column("address", sa.String(), nullable=True),
        sa.Column("city", sa.String(), nullable=True),
        sa.Column("state", sa.String(), nullable=True),
        sa.Column("postal_code", sa.String(), nullable=True),
        sa.Column("country_id", sa.Integer(), sa.ForeignKey("countries.id"), nullable=False),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("approval_status", sa.String(), nullable=False, server_default="Pending"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("approved_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(op.f("ix_branches_business_id"), "branches", ["business_id"], unique=False)
    op.create_index(op.f("ix_branches_approval_status"), "branches", ["approval_status"], unique=False)
    op.create_index(op.f("ix_branches_city"), "branches", ["city"], unique=False)

    op.create_table(
        "branch_working_hours",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("opening_time", sa.Time(), nullable=True),
        sa.Column("closing_time", sa.Time(), nullable=True),
        sa.Column("is_closed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("branch_id", "weekday", name="uq_branch_working_hours_branch_weekday"),
    )
    op.create_index(op.f("ix_branch_working_hours_branch_id"), "branch_working_hours", ["branch_id"], unique=False)

    op.create_table(
        "branch_assignments",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("business_member_id", sa.Integer(), sa.ForeignKey("business_members.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assigned_from", sa.DateTime(), nullable=False),
        sa.Column("assigned_to", sa.DateTime(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index(op.f("ix_branch_assignments_business_member_id"), "branch_assignments", ["business_member_id"], unique=False)
    op.create_index(op.f("ix_branch_assignments_branch_id"), "branch_assignments", ["branch_id"], unique=False)
    op.create_index(
        "uq_branch_assignments_one_current",
        "branch_assignments",
        ["business_member_id"],
        unique=True,
        postgresql_where=sa.text("is_current = true"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("branch_assignments")
    op.drop_table("branch_working_hours")
    op.drop_table("branches")
