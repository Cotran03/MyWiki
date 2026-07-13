"""validate trash purge order

Revision ID: d9e7d6a773e8
Revises: edfec9d7ddb0
Create Date: 2026-07-14 01:16:26.757108

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "d9e7d6a773e8"
down_revision = "edfec9d7ddb0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        op.f("ck_documents_valid_purge_order"),
        "documents",
        "purge_after IS NULL OR purge_after >= trashed_at",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_documents_valid_purge_order"),
        "documents",
        type_="check",
    )
