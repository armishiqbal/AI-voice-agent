from alembic import op
import sqlalchemy as sa


revision = "0003_outbox_leases"
down_revision = "0002_outbox_retries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("outbox_events", sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("outbox_events", sa.Column("claimed_by", sa.String(64), nullable=True))
    op.create_index("ix_outbox_events_claimed_at", "outbox_events", ["claimed_at"])


def downgrade() -> None:
    op.drop_index("ix_outbox_events_claimed_at", table_name="outbox_events")
    op.drop_column("outbox_events", "claimed_by")
    op.drop_column("outbox_events", "claimed_at")
