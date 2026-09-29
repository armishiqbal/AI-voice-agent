import sqlalchemy as sa

from alembic import op

revision = "0023_lead_follow_up_enqueued"
down_revision = "0022_property_source_unverified"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("leads")}
    if "follow_up_enqueued_at" not in columns:
        op.add_column(
            "leads",
            sa.Column("follow_up_enqueued_at", sa.DateTime(timezone=True), nullable=True),
        )
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("leads")}
    if "ix_leads_follow_up_enqueued_at" not in indexes:
        op.create_index("ix_leads_follow_up_enqueued_at", "leads", ["follow_up_enqueued_at"])


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("leads")}
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("leads")}
    if "ix_leads_follow_up_enqueued_at" in indexes:
        op.drop_index("ix_leads_follow_up_enqueued_at", table_name="leads")
    if "follow_up_enqueued_at" in columns:
        op.drop_column("leads", "follow_up_enqueued_at")
