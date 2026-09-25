from alembic import op
import sqlalchemy as sa


revision = "0009_leads"
down_revision = "0008_transcript_retention"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "leads",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("client_name", sa.String(100), nullable=False),
        sa.Column("contact_email_ciphertext", sa.Text(), nullable=False),
        sa.Column("intent", sa.String(32), nullable=False),
        sa.Column("city", sa.String(64), nullable=True),
        sa.Column("area", sa.String(128), nullable=True),
        sa.Column("budget_pkr", sa.Integer(), nullable=True),
        sa.Column("notes_redacted", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False, server_default="new"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_leads_intent", "leads", ["intent"])
    op.create_index("ix_leads_status", "leads", ["status"])
    op.create_index("ix_leads_created_at", "leads", ["created_at"])


def downgrade() -> None:
    for column in ("created_at", "status", "intent"):
        op.drop_index(f"ix_leads_{column}", table_name="leads")
    op.drop_table("leads")
