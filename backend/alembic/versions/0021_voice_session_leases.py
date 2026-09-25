"""Enforce distributed active voice-session limits with expiring leases."""

from alembic import op
import sqlalchemy as sa


revision = "0021_voice_session_leases"
down_revision = "0020_voice_session_credentials"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "voice_session_quota_locks",
        sa.Column("scope", sa.String(length=80), nullable=False),
        sa.Column("touched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("scope"),
    )
    op.create_table(
        "voice_session_leases",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("client_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    op.create_index(
        "ix_voice_session_leases_client_fingerprint",
        "voice_session_leases",
        ["client_fingerprint"],
    )
    op.create_index(
        "ix_voice_session_leases_created_at", "voice_session_leases", ["created_at"]
    )
    op.create_index(
        "ix_voice_session_leases_expires_at", "voice_session_leases", ["expires_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_voice_session_leases_expires_at", table_name="voice_session_leases")
    op.drop_index("ix_voice_session_leases_created_at", table_name="voice_session_leases")
    op.drop_index(
        "ix_voice_session_leases_client_fingerprint", table_name="voice_session_leases"
    )
    op.drop_table("voice_session_leases")
    op.drop_table("voice_session_quota_locks")
