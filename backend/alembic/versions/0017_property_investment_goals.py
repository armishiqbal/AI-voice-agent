"""Persist structured investment goals for deterministic recommendations."""

import sqlalchemy as sa

from alembic import op

revision = "0017_property_investment_goals"
down_revision = "0016_conversation_tool_results"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "properties",
        sa.Column("investment_goals", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("properties", "investment_goals")

