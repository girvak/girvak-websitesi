"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Purpose: <one line: what this revision changes>
Backward compatible: <yes | no — no is only legal as the contract half of expand/contract>
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
${imports if imports else ""}
revision: str = ${repr(up_revision)}
down_revision: str | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    op.execute("SET lock_timeout = '3s'")
    op.execute("SET statement_timeout = '60s'")
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    op.execute("SET lock_timeout = '3s'")
    op.execute("SET statement_timeout = '60s'")
    ${downgrades if downgrades else "pass"}
