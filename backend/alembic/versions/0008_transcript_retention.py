import sqlalchemy as sa

from alembic import op

revision = "0008_transcript_retention"
down_revision = "0007_appointment_action_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversation_transcripts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("conversation_id", sa.String(64), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("text_redacted", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("conversation_id", "created_at", "expires_at"):
        op.create_index(f"ix_conversation_transcripts_{column}", "conversation_transcripts", [column])


def downgrade() -> None:
    for column in ("expires_at", "created_at", "conversation_id"):
        op.drop_index(f"ix_conversation_transcripts_{column}", table_name="conversation_transcripts")
    op.drop_table("conversation_transcripts")
