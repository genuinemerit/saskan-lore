"""add eval question_id

Revision ID: e7f3a2c91d40
Revises: c2d4a8f3e610
Create Date: 2026-04-03 12:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7f3a2c91d40"
down_revision: Union[str, None] = "c2d4a8f3e610"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("eval_questions", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("question_id", sa.String(50), nullable=False, server_default="")
        )
        batch_op.create_unique_constraint("uq_eval_questions_question_id", ["question_id"])


def downgrade() -> None:
    with op.batch_alter_table("eval_questions", schema=None) as batch_op:
        batch_op.drop_constraint("uq_eval_questions_question_id", type_="unique")
        batch_op.drop_column("question_id")
