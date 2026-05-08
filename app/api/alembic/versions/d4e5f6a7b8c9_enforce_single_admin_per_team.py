"""enforce_single_admin_per_team

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-08 13:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX uq_team_one_admin ON team_members (team_id) WHERE role = 'admin'"
    )


def downgrade() -> None:
    op.drop_index("uq_team_one_admin", table_name="team_members")
