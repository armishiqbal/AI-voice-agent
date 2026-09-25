"""Persist bounded deterministic tool results in conversation snapshots."""

from alembic import op
import sqlalchemy as sa


revision = "0016_conversation_tool_results"
down_revision = "0015_appointment_contact_phone"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversation_states",
        sa.Column("tool_results", sa.JSON(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("conversation_states", "tool_results")

