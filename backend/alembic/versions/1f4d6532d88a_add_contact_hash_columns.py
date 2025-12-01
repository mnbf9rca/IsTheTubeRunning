"""add_contact_hash_columns

Adds indexed contact_hash column to email_addresses and phone_numbers tables
to enable PII-safe logging and telemetry.

Revision ID: 1f4d6532d88a
Revises: cea4031bd399
Create Date: 2025-12-01 13:25:14.769254

"""

import hashlib
from collections.abc import Sequence

from alembic import op
from sqlalchemy import Column, String, text

# revision identifiers, used by Alembic.
revision: str = "1f4d6532d88a"
down_revision: str | Sequence[str] | None = "cea4031bd399"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _hash_pii(value: str) -> str:
    """Hash PII value (same as app.utils.pii.hash_pii)."""
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def upgrade() -> None:
    """Upgrade schema."""
    # Step 1: Add contact_hash columns as nullable
    op.add_column(
        "email_addresses",
        Column("contact_hash", String(length=12), nullable=True),
    )
    op.add_column(
        "phone_numbers",
        Column("contact_hash", String(length=12), nullable=True),
    )

    # Step 2: Backfill existing records
    # Get database connection
    conn = op.get_bind()

    # Backfill email_addresses
    emails = conn.execute(text("SELECT id, email FROM email_addresses WHERE contact_hash IS NULL")).fetchall()
    for row in emails:
        contact_hash = _hash_pii(row.email)
        conn.execute(
            text("UPDATE email_addresses SET contact_hash = :hash WHERE id = :id"),
            {"hash": contact_hash, "id": row.id},
        )

    # Backfill phone_numbers
    phones = conn.execute(text("SELECT id, phone FROM phone_numbers WHERE contact_hash IS NULL")).fetchall()
    for row in phones:
        contact_hash = _hash_pii(row.phone)
        conn.execute(
            text("UPDATE phone_numbers SET contact_hash = :hash WHERE id = :id"),
            {"hash": contact_hash, "id": row.id},
        )

    # Step 3: Set columns to NOT NULL
    op.alter_column("email_addresses", "contact_hash", nullable=False)
    op.alter_column("phone_numbers", "contact_hash", nullable=False)

    # Step 4: Create indexes
    op.create_index("ix_email_addresses_contact_hash", "email_addresses", ["contact_hash"])
    op.create_index("ix_phone_numbers_contact_hash", "phone_numbers", ["contact_hash"])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes first
    op.drop_index("ix_phone_numbers_contact_hash", table_name="phone_numbers")
    op.drop_index("ix_email_addresses_contact_hash", table_name="email_addresses")

    # Drop columns
    op.drop_column("phone_numbers", "contact_hash")
    op.drop_column("email_addresses", "contact_hash")
