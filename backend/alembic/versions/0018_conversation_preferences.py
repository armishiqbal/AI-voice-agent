"""Persist structured preference fields used by deterministic recommendation ranking."""

from alembic import op
import sqlalchemy as sa


revision = "0018_conversation_preferences"
down_revision = "0017_property_investment_goals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("conversation_states", sa.Column("bedrooms", sa.Integer(), nullable=True))
    op.add_column(
        "conversation_states",
        sa.Column("amenities", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "conversation_states",
        sa.Column("investment_goal", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversation_states", "investment_goal")
    op.drop_column("conversation_states", "amenities")
    op.drop_column("conversation_states", "bedrooms")

