"""Mark the user Remya as PMO.

PMO users see the Add/Edit Assignee and Add/Edit Tracks right sidebar tabs.
Usernames are stored lower-case, so the match is case-insensitive. If the account
does not exist yet the statement is a no-op.

Revision ID: 017_make_remya_pmo
Revises: 016_add_user_is_pmo
Create Date: 2026-10-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "017_make_remya_pmo"
down_revision: Union[str, None] = "016_add_user_is_pmo"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text("UPDATE users SET is_pmo = TRUE WHERE lower(username) = 'remya'")
    )


def downgrade() -> None:
    op.execute(
        sa.text("UPDATE users SET is_pmo = FALSE WHERE lower(username) = 'remya'")
    )
