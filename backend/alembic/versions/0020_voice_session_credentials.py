"""Persist hashed one-use voice tickets and cross-worker issue limits."""

import sqlalchemy as sa

from alembic import op

revision = "0020_voice_session_credentials"
down_revision = "0019_lead_follow_up"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "voice_session_tickets",
        sa.Column("client_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("origin", sa.String(length=512), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    op.create_index(
        "ix_voice_session_tickets_client_fingerprint",
        "voice_session_tickets",
        ["client_fingerprint"],
    )
    op.create_index(
        "ix_voice_session_tickets_created_at", "voice_session_tickets", ["created_at"]
    )
    op.create_index(
        "ix_voice_session_tickets_expires_at", "voice_session_tickets", ["expires_at"]
    )
    op.create_table(
        "voice_session_rate_limits",
        sa.Column("client_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("client_fingerprint"),
    )
    op.create_index(
        "ix_voice_session_rate_limits_window_started_at",
        "voice_session_rate_limits",
        ["window_started_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_voice_session_rate_limits_window_started_at", table_name="voice_session_rate_limits"
    )
    op.drop_table("voice_session_rate_limits")
    op.drop_index("ix_voice_session_tickets_expires_at", table_name="voice_session_tickets")
    op.drop_index("ix_voice_session_tickets_created_at", table_name="voice_session_tickets")
    op.drop_index(
        "ix_voice_session_tickets_client_fingerprint", table_name="voice_session_tickets"
    )
    op.drop_table("voice_session_tickets")
