"""Persist an optional consented appointment phone number encrypted at application level."""

from alembic import op
import sqlalchemy as sa


revision = "0015_appointment_contact_phone"
down_revision = "0014_active_appointment_slot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("appointments", sa.Column("contact_phone_ciphertext", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("appointments", "contact_phone_ciphertext")

