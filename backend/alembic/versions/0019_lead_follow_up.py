"""Persist optional CRM follow-up reminders for consented leads."""

import sqlalchemy as sa

from alembic import op

revision = "0019_lead_follow_up"
down_revision = "0018_conversation_preferences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "leads",
        sa.Column("follow_up_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_leads_follow_up_at", "leads", ["follow_up_at"])


def downgrade() -> None:
    op.drop_index("ix_leads_follow_up_at", table_name="leads")
    op.drop_column("leads", "follow_up_at")

