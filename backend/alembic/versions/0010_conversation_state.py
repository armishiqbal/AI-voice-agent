from alembic import op
import sqlalchemy as sa


revision = "0010_conversation_state"
down_revision = "0009_leads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversation_states",
        sa.Column("conversation_id", sa.String(64), primary_key=True),
        sa.Column("history", sa.JSON(), nullable=False),
        sa.Column("detected_language", sa.String(16), nullable=False),
        sa.Column("lead_profile", sa.JSON(), nullable=False),
        sa.Column("budget", sa.Integer(), nullable=True),
        sa.Column("city", sa.String(64), nullable=True),
        sa.Column("area", sa.String(128), nullable=True),
        sa.Column("intent", sa.String(32), nullable=False),
        sa.Column("retrieved_sources", sa.JSON(), nullable=False),
        sa.Column("selected_property_ids", sa.JSON(), nullable=False),
        sa.Column("appointment_status", sa.String(32), nullable=True),
        sa.Column("escalation_reason", sa.String(64), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_conversation_states_updated_at", "conversation_states", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_conversation_states_updated_at", table_name="conversation_states")
    op.drop_table("conversation_states")
