"""Add website-owned listing metadata and public media records.

Revision ID: 0024_public_property_catalog
Revises: 0023_lead_follow_up_enqueued
"""

import sqlalchemy as sa

from alembic import op

revision = "0024_public_property_catalog"
down_revision = "0023_lead_follow_up_enqueued"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("properties") as batch_op:
        batch_op.alter_column(
            "price_pkr",
            existing_type=sa.Integer(),
            type_=sa.BigInteger(),
            existing_nullable=False,
        )
        batch_op.add_column(sa.Column("slug", sa.String(length=180), nullable=True))
        batch_op.add_column(
            sa.Column("description", sa.Text(), server_default="", nullable=False)
        )
        batch_op.add_column(sa.Column("transaction_type", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("property_type", sa.String(length=24), nullable=True))
        batch_op.add_column(sa.Column("bathrooms", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "publication_status", sa.String(length=16), server_default="draft", nullable=False
            )
        )
        batch_op.add_column(
            sa.Column(
                "availability_status",
                sa.String(length=20),
                server_default="unconfirmed",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column("availability_confirmed_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("content_permission_confirmed_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("edit_version", sa.Integer(), server_default="1", nullable=False)
        )
        batch_op.add_column(sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("latitude", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("longitude", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("assigned_staff_id", sa.String(length=128), nullable=True))
        batch_op.create_unique_constraint("uq_properties_slug", ["slug"])

    op.create_index("ix_properties_transaction_type", "properties", ["transaction_type"])
    op.create_index("ix_properties_property_type", "properties", ["property_type"])
    op.create_index("ix_properties_publication_status", "properties", ["publication_status"])
    op.create_index("ix_properties_availability_status", "properties", ["availability_status"])
    op.create_index("ix_properties_assigned_staff_id", "properties", ["assigned_staff_id"])
    op.create_index(
        "ix_properties_availability_confirmed_at", "properties", ["availability_confirmed_at"]
    )
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE properties SET availability_status = "
            "CASE WHEN available THEN 'available' ELSE 'unavailable' END"
        )
    )
    bind.execute(
        sa.text(
            "UPDATE properties SET transaction_type = purpose "
            "WHERE purpose IN ('sale', 'rent')"
        )
    )

    op.create_table(
        "property_media",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "property_id",
            sa.String(length=64),
            sa.ForeignKey("properties.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("original_object_path", sa.Text(), nullable=False),
        sa.Column("derivative_object_path", sa.Text(), nullable=True),
        sa.Column("public_url", sa.Text(), nullable=True),
        sa.Column("alt_text", sa.String(length=300), server_default="", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("processing_status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("is_public", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_property_media_property_id", "property_media", ["property_id"])
    op.create_index("ix_property_media_processing_status", "property_media", ["processing_status"])
    op.create_index("ix_property_media_is_public", "property_media", ["is_public"])
    op.create_index(
        "ix_property_media_public_order",
        "property_media",
        ["property_id", "is_public", "sort_order"],
    )

    op.create_table(
        "listing_verifications",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "property_id",
            sa.String(length=64),
            sa.ForeignKey("properties.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("review_scope", sa.String(length=160), nullable=False),
        sa.Column("reviewer_id", sa.String(length=128), nullable=False),
        sa.Column("evidence_reference", sa.Text(), nullable=True),
        sa.Column("result", sa.String(length=20), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("public_source_url", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_listing_verifications_property_id", "listing_verifications", ["property_id"]
    )
    op.create_index("ix_listing_verifications_result", "listing_verifications", ["result"])
    op.create_index(
        "ix_listing_verifications_reviewed_at", "listing_verifications", ["reviewed_at"]
    )
    op.create_index(
        "ix_listing_verifications_latest",
        "listing_verifications",
        ["property_id", "reviewed_at"],
    )

    op.create_table(
        "staff_users",
        sa.Column("provider_subject", sa.String(length=128), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_staff_users_role", "staff_users", ["role"])
    op.create_index("ix_staff_users_is_active", "staff_users", ["is_active"])

    op.create_table(
        "website_inquiries",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("idempotency_key", sa.String(length=36), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "property_id",
            sa.String(length=64),
            sa.ForeignKey("properties.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("request_type", sa.String(length=20), nullable=False),
        sa.Column("client_name_ciphertext", sa.Text(), nullable=False),
        sa.Column("contact_email_ciphertext", sa.Text(), nullable=True),
        sa.Column("contact_phone_ciphertext", sa.Text(), nullable=True),
        sa.Column("contact_preference", sa.String(length=16), nullable=False),
        sa.Column("message_redacted", sa.Text(), server_default="", nullable=False),
        sa.Column("consent_version", sa.String(length=64), nullable=False),
        sa.Column("consent_purpose", sa.String(length=64), nullable=False),
        sa.Column("consent_channel", sa.String(length=32), nullable=False),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("workflow_status", sa.String(length=32), server_default="new", nullable=False),
        sa.Column(
            "delivery_status", sa.String(length=24), server_default="not_configured", nullable=False
        ),
        sa.Column("edit_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("assigned_staff_id", sa.String(length=128), nullable=True),
        sa.Column("follow_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closing_outcome", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_website_inquiries_idempotency_key", "website_inquiries", ["idempotency_key"], unique=True
    )
    op.create_index("ix_website_inquiries_property_id", "website_inquiries", ["property_id"])
    op.create_index("ix_website_inquiries_request_type", "website_inquiries", ["request_type"])
    op.create_index("ix_website_inquiries_workflow_status", "website_inquiries", ["workflow_status"])
    op.create_index(
        "ix_website_inquiries_assigned_staff_id", "website_inquiries", ["assigned_staff_id"]
    )
    op.create_index("ix_website_inquiries_created_at", "website_inquiries", ["created_at"])
    op.create_index("ix_website_inquiries_expires_at", "website_inquiries", ["expires_at"])

    op.create_table(
        "website_inquiry_activity",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "inquiry_id",
            sa.String(length=36),
            sa.ForeignKey("website_inquiries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("actor_staff_id", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("details_redacted", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_website_inquiry_activity_inquiry_id", "website_inquiry_activity", ["inquiry_id"]
    )
    op.create_index(
        "ix_website_inquiry_activity_created_at", "website_inquiry_activity", ["created_at"]
    )


def downgrade() -> None:
    op.drop_table("website_inquiry_activity")
    op.drop_table("website_inquiries")
    op.drop_table("staff_users")
    op.drop_table("listing_verifications")
    op.drop_table("property_media")
    op.drop_index("ix_properties_availability_confirmed_at", table_name="properties")
    op.drop_index("ix_properties_assigned_staff_id", table_name="properties")
    op.drop_index("ix_properties_availability_status", table_name="properties")
    op.drop_index("ix_properties_publication_status", table_name="properties")
    op.drop_index("ix_properties_property_type", table_name="properties")
    op.drop_index("ix_properties_transaction_type", table_name="properties")
    with op.batch_alter_table("properties") as batch_op:
        batch_op.drop_constraint("uq_properties_slug", type_="unique")
        batch_op.drop_column("longitude")
        batch_op.drop_column("assigned_staff_id")
        batch_op.drop_column("latitude")
        batch_op.drop_column("published_at")
        batch_op.drop_column("edit_version")
        batch_op.drop_column("availability_confirmed_at")
        batch_op.drop_column("content_permission_confirmed_at")
        batch_op.drop_column("availability_status")
        batch_op.drop_column("publication_status")
        batch_op.drop_column("bathrooms")
        batch_op.drop_column("property_type")
        batch_op.drop_column("transaction_type")
        batch_op.drop_column("description")
        batch_op.drop_column("slug")
        batch_op.alter_column(
            "price_pkr",
            existing_type=sa.BigInteger(),
            type_=sa.Integer(),
            existing_nullable=False,
        )
