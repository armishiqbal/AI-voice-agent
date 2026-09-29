import sqlalchemy as sa

from alembic import op

revision = "0011_conversation_state_retention"
down_revision = "0010_conversation_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversation_states",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_conversation_states_expires_at", "conversation_states", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_conversation_states_expires_at", table_name="conversation_states")
    op.drop_column("conversation_states", "expires_at")
