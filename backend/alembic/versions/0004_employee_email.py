from alembic import op
import sqlalchemy as sa


revision = "0004_employee_email"
down_revision = "0003_outbox_leases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("appointments", sa.Column("employee_email", sa.String(320), nullable=True))


def downgrade() -> None:
    op.drop_column("appointments", "employee_email")
