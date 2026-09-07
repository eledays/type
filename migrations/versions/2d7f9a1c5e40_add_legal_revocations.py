"""add legal consent revocation records

Revision ID: 2d7f9a1c5e40
Revises: 6a4c8e2f1b90
Create Date: 2026-09-07 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "2d7f9a1c5e40"
down_revision = "6a4c8e2f1b90"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Allow revocation history and repeated acceptance of a document set."""
    with op.batch_alter_table("legal_acceptance", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_index(
            "ix_legal_acceptance_revoked_at", ["revoked_at"], unique=False
        )
        batch_op.drop_constraint(
            "uq_legal_acceptance_user_versions", type_="unique"
        )


def downgrade() -> None:
    """Remove revocation support."""
    with op.batch_alter_table("legal_acceptance", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "uq_legal_acceptance_user_versions",
            [
                "user_id",
                "terms_version",
                "privacy_version",
                "personal_data_consent_version",
            ],
        )
        batch_op.drop_index("ix_legal_acceptance_revoked_at")
        batch_op.drop_column("revoked_at")
