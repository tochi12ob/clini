"""added email verificationD

Revision ID: 08e8fb804be9
Revises: 2231e434e56a
Create Date: 2025-07-08 09:36:18.898721

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '08e8fb804be9'
down_revision: Union[str, None] = '2231e434e56a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # This migration previously added 'email_verification_code' and 'email_verified' columns to 'clinics',
    # but these columns are already added in migration fb857fd5cc8b_add_hash_to_staff_and_clinic_table.py.
    # No schema changes are needed here to avoid duplicate column errors.
    pass
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # No schema changes to revert since nothing was applied in upgrade.
    pass
    # ### end Alembic commands ###
