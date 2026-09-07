"""add legal acceptance audit records

Revision ID: 6a4c8e2f1b90
Revises: c4e82a7d913f
Create Date: 2026-09-07 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "6a4c8e2f1b90"
down_revision = "c4e82a7d913f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create immutable records of accepted legal document versions."""
    op.create_table(
        "legal_acceptance",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("terms_version", sa.String(length=32), nullable=False),
        sa.Column("privacy_version", sa.String(length=32), nullable=False),
        sa.Column(
            "personal_data_consent_version",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "terms_version",
            "privacy_version",
            "personal_data_consent_version",
            name="uq_legal_acceptance_user_versions",
        ),
    )
    op.create_index(
        "ix_legal_acceptance_user_id",
        "legal_acceptance",
        ["user_id"],
    )


def downgrade() -> None:
    """Remove legal acceptance audit records."""
    op.drop_index(
        "ix_legal_acceptance_user_id", table_name="legal_acceptance"
    )
    op.drop_table("legal_acceptance")
