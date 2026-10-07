"""Invited agency marketplace ownership, moderation and customer records."""

import sqlalchemy as sa
from alembic import op

revision = "0026_marketplace"
down_revision = "0025_area_guides_and_search_indexes"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "marketplace_rate_windows",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("window", sa.Integer(), primary_key=True),
        sa.Column("hits", sa.Integer(), nullable=False),
    )
    op.create_table(
        "viewing_otp_challenges",
        sa.Column("email_hash", sa.String(64), primary_key=True),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
    )
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("slug", sa.String(length=128), primary_key=False, nullable=False, unique=True),
        sa.Column("name", sa.String(length=200), primary_key=False, nullable=False),
        sa.Column("status", sa.String(length=20), primary_key=False, nullable=False),
        sa.Column("description", sa.Text(), primary_key=False, nullable=False),
        sa.Column("contact_email", sa.String(length=254), primary_key=False, nullable=True),
        sa.Column("contact_phone", sa.String(length=32), primary_key=False, nullable=True),
        sa.Column("coverage", sa.JSON(), primary_key=False, nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), primary_key=False, nullable=True),
        sa.Column("edit_version", sa.Integer(), primary_key=False, nullable=False),
    )
    op.create_index("ix_organizations_status", "organizations", ["status"], unique=False)
    op.create_table(
        "organization_memberships",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id"),
            primary_key=False,
            nullable=False,
        ),
        sa.Column("subject", sa.String(length=128), primary_key=False, nullable=False),
        sa.Column("email", sa.String(length=254), primary_key=False, nullable=False),
        sa.Column("role", sa.String(length=20), primary_key=False, nullable=False),
        sa.Column("active", sa.Boolean(), primary_key=False, nullable=False),
        sa.Column("display_name", sa.String(length=128), primary_key=False, nullable=False),
        sa.Column("slug", sa.String(length=160), primary_key=False, nullable=True, unique=True),
        sa.Column("profile_approved", sa.Boolean(), primary_key=False, nullable=False),
        sa.Column("languages", sa.JSON(), primary_key=False, nullable=False),
    )
    op.create_index(
        "ix_organization_memberships_organization_id",
        "organization_memberships",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "uq_membership_org_subject",
        "organization_memberships",
        ["organization_id", "subject"],
        unique=True,
    )
    op.create_index(
        "ix_organization_memberships_subject", "organization_memberships", ["subject"], unique=False
    )
    op.create_table(
        "marketplace_locations",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("city", sa.String(length=64), primary_key=False, nullable=False),
        sa.Column("city_slug", sa.String(length=64), primary_key=False, nullable=False),
        sa.Column("area", sa.String(length=128), primary_key=False, nullable=False),
        sa.Column("area_slug", sa.String(length=128), primary_key=False, nullable=False),
        sa.Column("aliases", sa.JSON(), primary_key=False, nullable=False),
        sa.Column("reviewed", sa.Boolean(), primary_key=False, nullable=False),
        sa.Column("sqft_per_marla", sa.Integer(), primary_key=False, nullable=True),
    )
    op.create_index(
        "uq_location_city_area", "marketplace_locations", ["city_slug", "area_slug"], unique=True
    )
    op.create_index(
        "ix_marketplace_locations_city", "marketplace_locations", ["city"], unique=False
    )
    op.create_table(
        "listing_revisions",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "property_id",
            sa.String(length=64),
            sa.ForeignKey("properties.id"),
            primary_key=False,
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id"),
            primary_key=False,
            nullable=False,
        ),
        sa.Column("proposed", sa.JSON(), primary_key=False, nullable=False),
        sa.Column("base_version", sa.Integer(), primary_key=False, nullable=False),
        sa.Column("status", sa.String(length=20), primary_key=False, nullable=False),
        sa.Column("submitted_by", sa.String(length=128), primary_key=False, nullable=False),
        sa.Column("reviewed_by", sa.String(length=128), primary_key=False, nullable=True),
        sa.Column("review_note", sa.Text(), primary_key=False, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), primary_key=False, nullable=False),
    )
    op.create_index(
        "ix_listing_revisions_property_id", "listing_revisions", ["property_id"], unique=False
    )
    op.create_index(
        "ix_listing_revisions_organization_id",
        "listing_revisions",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "uq_revision_submitted_property",
        "listing_revisions",
        ["property_id"],
        unique=True,
        sqlite_where=sa.text("status = 'submitted'"),
        postgresql_where=sa.text("status = 'submitted'"),
    )
    op.create_table(
        "agent_schedules",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("subject", sa.String(length=128), primary_key=False, nullable=False),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id"),
            primary_key=False,
            nullable=False,
        ),
        sa.Column("weekday", sa.Integer(), primary_key=False, nullable=False),
        sa.Column("start_minute", sa.Integer(), primary_key=False, nullable=False),
        sa.Column("end_minute", sa.Integer(), primary_key=False, nullable=False),
        sa.Column("approved", sa.Boolean(), primary_key=False, nullable=False),
        sa.Column("exception_date", sa.String(length=10), primary_key=False, nullable=True),
        sa.Column("unavailable", sa.Boolean(), primary_key=False, nullable=False),
    )
    op.create_index("ix_agent_schedules_subject", "agent_schedules", ["subject"], unique=False)
    op.create_index(
        "ix_agent_schedules_organization_id", "agent_schedules", ["organization_id"], unique=False
    )
    op.create_table(
        "application_sessions",
        sa.Column("token_hash", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("subject", sa.String(length=128), primary_key=False, nullable=False),
        sa.Column("email", sa.String(length=254), primary_key=False, nullable=False),
        sa.Column("assurance", sa.String(length=8), primary_key=False, nullable=False),
        sa.Column("csrf_hash", sa.String(length=64), primary_key=False, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.Column("revoked", sa.Boolean(), primary_key=False, nullable=False),
    )
    op.create_index(
        "ix_application_sessions_subject", "application_sessions", ["subject"], unique=False
    )
    op.create_table(
        "customer_favorites",
        sa.Column("subject", sa.String(length=128), primary_key=True, nullable=False),
        sa.Column(
            "property_id",
            sa.String(length=64),
            sa.ForeignKey("properties.id"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), primary_key=False, nullable=False),
    )
    op.create_table(
        "customer_profiles",
        sa.Column("subject", sa.String(128), primary_key=True),
        sa.Column("email_ciphertext", sa.Text(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "saved_searches",
        sa.Column("unsubscribe_ciphertext", sa.Text(), nullable=True),
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("subject", sa.String(length=128), primary_key=False, nullable=False),
        sa.Column("name", sa.String(length=100), primary_key=False, nullable=False),
        sa.Column("filters", sa.JSON(), primary_key=False, nullable=False),
        sa.Column("notification_consent", sa.Boolean(), primary_key=False, nullable=False),
        sa.Column("consent_version", sa.String(length=64), primary_key=False, nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.Column("active", sa.Boolean(), primary_key=False, nullable=False),
        sa.Column(
            "unsubscribe_hash", sa.String(length=64), primary_key=False, nullable=False, unique=True
        ),
    )
    op.create_index("ix_saved_searches_subject", "saved_searches", ["subject"], unique=False)
    op.create_table(
        "marketplace_audit",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("actor", sa.String(length=128), primary_key=False, nullable=False),
        sa.Column("organization_id", sa.String(length=36), primary_key=False, nullable=True),
        sa.Column("action", sa.String(length=64), primary_key=False, nullable=False),
        sa.Column("resource_id", sa.String(length=128), primary_key=False, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), primary_key=False, nullable=False),
    )
    op.create_table(
        "listing_reports",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "property_id",
            sa.String(length=64),
            sa.ForeignKey("properties.id"),
            primary_key=False,
            nullable=False,
        ),
        sa.Column("category", sa.String(length=32), primary_key=False, nullable=False),
        sa.Column("status", sa.String(length=20), primary_key=False, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), primary_key=False, nullable=False),
    )
    op.create_index(
        "ix_listing_reports_property_id", "listing_reports", ["property_id"], unique=False
    )
    op.create_table(
        "alert_deliveries",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "search_id",
            sa.String(length=36),
            sa.ForeignKey("saved_searches.id"),
            primary_key=False,
            nullable=False,
        ),
        sa.Column(
            "property_id",
            sa.String(length=64),
            sa.ForeignKey("properties.id"),
            primary_key=False,
            nullable=False,
        ),
        sa.Column("publication_key", sa.String(length=64), primary_key=False, nullable=False),
        sa.Column("status", sa.String(length=20), primary_key=False, nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), primary_key=False, nullable=True),
    )
    op.create_index(
        "ix_alert_deliveries_search_id", "alert_deliveries", ["search_id"], unique=False
    )
    op.create_index(
        "uq_alert_search_publication",
        "alert_deliveries",
        ["search_id", "property_id", "publication_key"],
        unique=True,
    )
    op.add_column("properties", sa.Column("organization_id", sa.String(length=36), nullable=True))
    op.add_column("properties", sa.Column("classification", sa.String(length=16), nullable=True))
    op.add_column("properties", sa.Column("rental_period", sa.String(length=16), nullable=True))
    op.add_column(
        "properties",
        sa.Column("coordinates_approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "website_inquiries", sa.Column("organization_id", sa.String(length=36), nullable=True)
    )
    op.add_column(
        "website_inquiries", sa.Column("agent_subject", sa.String(length=128), nullable=True)
    )
    op.add_column("appointments", sa.Column("organization_id", sa.String(length=36), nullable=True))
    op.add_column("appointments", sa.Column("agent_subject", sa.String(length=128), nullable=True))
    op.add_column("appointments", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_appointments_closed_at", "appointments", ["closed_at"], unique=False)
    op.execute("UPDATE appointments SET closed_at = CURRENT_TIMESTAMP WHERE status = 'cancelled'")
    op.execute(
        "INSERT INTO organizations (id, slug, name, status, description, coverage, edit_version) VALUES ('awaaz', 'awaaz-estate', 'Awaaz Estate', 'pending', '', '[]', 1)"
    )
    for table in ("properties", "website_inquiries", "appointments"):
        op.execute(
            sa.text(
                f"UPDATE {table} SET organization_id = :org WHERE organization_id IS NULL"
            ).bindparams(org="awaaz")
        )
    op.execute("UPDATE properties SET publication_status = 'draft' WHERE organization_id = 'awaaz'")


def downgrade():
    raise RuntimeError("Marketplace rollback is flag based; retain ownership and accepted requests")
