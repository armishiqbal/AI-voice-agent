import sqlalchemy as sa

from alembic import op

revision = "0013_appointment_client_name"
down_revision = "0012_property_local_services"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A server default keeps upgrades safe for existing appointments. New API
    # bookings always write the consented client name explicitly.
    op.add_column(
        "appointments",
        sa.Column("client_name", sa.String(length=100), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("appointments", "client_name")
