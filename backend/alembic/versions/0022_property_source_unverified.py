import sqlalchemy as sa

from alembic import op

revision = "0022_property_source_unverified"
down_revision = "0021_voice_session_leases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("properties") as batch_op:
        batch_op.alter_column(
            "source",
            existing_type=sa.String(255),
            existing_nullable=False,
            existing_server_default=sa.text("'demo-fixture'"),
            server_default=sa.text("'unverified'"),
        )


def downgrade() -> None:
    with op.batch_alter_table("properties") as batch_op:
        batch_op.alter_column(
            "source",
            existing_type=sa.String(255),
            existing_nullable=False,
            existing_server_default=sa.text("'unverified'"),
            server_default=sa.text("'demo-fixture'"),
        )
