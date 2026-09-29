import sqlalchemy as sa

from alembic import op

revision = "0006_tool_audit_events"
down_revision = "0005_import_provenance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tool_audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("reference", sa.String(64), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("action", "status", "reference", "created_at"):
        op.create_index(f"ix_tool_audit_events_{column}", "tool_audit_events", [column])


def downgrade() -> None:
    for column in ("created_at", "reference", "status", "action"):
        op.drop_index(f"ix_tool_audit_events_{column}", table_name="tool_audit_events")
    op.drop_table("tool_audit_events")
