"""add staff invitation fields to business_members

Revision ID: 7f4c06f46451
Revises: ea4b777dab63
Create Date: 2026-08-19 00:00:00.000000

Adds the Milestone 3 (Employee/Staff Invitation & Onboarding) invitation
columns to business_members. See IMPLEMENTATION_DECISIONS.md ID-005/ID-009/
ID-010 for the reasoning:

- invitation_token_hash / invitation_token_expiry: per-membership invitation
  token. Lives on business_members rather than users, since the invite
  belongs to a specific membership, not the platform identity (ID-005).
- requires_credential_setup: recorded explicitly at invite time so
  accept-invitation can tell a brand-new placeholder User apart from an
  existing reused User, instead of inferring it from User.is_active, which
  is an unrelated pre-existing account-lock flag (ID-005).
- invited_branch_id: temporary staging column holding a pending Branch
  Manager invitation's target branch. The real BranchAssignment row is only
  created on successful acceptance (ID-010); this column is cleared once
  that happens. NULL for HR User invitations.

Purely additive: no existing column is altered, no data is migrated.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7f4c06f46451'
down_revision: Union[str, Sequence[str], None] = 'ea4b777dab63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("business_members", sa.Column("invitation_token_hash", sa.String(), nullable=True))
    op.add_column("business_members", sa.Column("invitation_token_expiry", sa.DateTime(), nullable=True))
    op.add_column(
        "business_members",
        sa.Column("requires_credential_setup", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "business_members",
        sa.Column("invited_branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=True),
    )
    op.create_index(
        op.f("ix_business_members_invitation_token_hash"),
        "business_members",
        ["invitation_token_hash"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_business_members_invitation_token_hash"), table_name="business_members")
    op.drop_column("business_members", "invited_branch_id")
    op.drop_column("business_members", "requires_credential_setup")
    op.drop_column("business_members", "invitation_token_expiry")
    op.drop_column("business_members", "invitation_token_hash")
