import sqlalchemy as sa

from alembic import op

revision = "0014_active_appointment_slot"
down_revision = "0013_appointment_client_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_appointments_active_employee_slot",
        "appointments",
        ["employee", "starts_at"],
        unique=True,
        sqlite_where=sa.text("status IN ('booked', 'rescheduled')"),
        postgresql_where=sa.text("status IN ('booked', 'rescheduled')"),
    )


def downgrade() -> None:
    op.drop_index("uq_appointments_active_employee_slot", table_name="appointments")
