from alembic import op
import sqlalchemy as sa


revision = "0007_appointment_action_idempotency"
down_revision = "0006_tool_audit_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "appointment_actions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("idempotency_key", sa.String(36), nullable=False, unique=True),
        sa.Column("reference", sa.String(64), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("result_status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_appointment_actions_idempotency_key", "appointment_actions", ["idempotency_key"])
    op.create_index("ix_appointment_actions_reference", "appointment_actions", ["reference"])


def downgrade() -> None:
    op.drop_index("ix_appointment_actions_reference", table_name="appointment_actions")
    op.drop_index("ix_appointment_actions_idempotency_key", table_name="appointment_actions")
    op.drop_table("appointment_actions")
