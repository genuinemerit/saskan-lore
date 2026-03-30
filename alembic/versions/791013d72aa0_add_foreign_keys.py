"""add foreign keys

Revision ID: 791013d72aa0
Revises: b6b114a51559
Create Date: 2026-03-30 12:55:11.999274

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '791013d72aa0'
down_revision: Union[str, None] = 'b6b114a51559'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('chunks', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_chunks_document_id', 'documents', ['document_id'], ['id']
        )

    with op.batch_alter_table('entity_aliases', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_entity_aliases_entity_id', 'entities', ['entity_id'], ['id']
        )

    with op.batch_alter_table('claims', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_claims_chunk_id', 'chunks', ['chunk_id'], ['id']
        )
        batch_op.create_foreign_key(
            'fk_claims_document_id', 'documents', ['document_id'], ['id']
        )

    with op.batch_alter_table('claim_entities', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_claim_entities_claim_id', 'claims', ['claim_id'], ['id']
        )
        batch_op.create_foreign_key(
            'fk_claim_entities_entity_id', 'entities', ['entity_id'], ['id']
        )

    with op.batch_alter_table('relationships', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_relationships_source_entity_id', 'entities', ['source_entity_id'], ['id']
        )
        batch_op.create_foreign_key(
            'fk_relationships_target_entity_id', 'entities', ['target_entity_id'], ['id']
        )
        batch_op.create_foreign_key(
            'fk_relationships_claim_id', 'claims', ['claim_id'], ['id']
        )

    with op.batch_alter_table('eval_results', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_eval_results_question_id', 'eval_questions', ['question_id'], ['id']
        )


def downgrade() -> None:
    with op.batch_alter_table('eval_results', schema=None) as batch_op:
        batch_op.drop_constraint('fk_eval_results_question_id', type_='foreignkey')

    with op.batch_alter_table('relationships', schema=None) as batch_op:
        batch_op.drop_constraint('fk_relationships_claim_id', type_='foreignkey')
        batch_op.drop_constraint('fk_relationships_target_entity_id', type_='foreignkey')
        batch_op.drop_constraint('fk_relationships_source_entity_id', type_='foreignkey')

    with op.batch_alter_table('claim_entities', schema=None) as batch_op:
        batch_op.drop_constraint('fk_claim_entities_entity_id', type_='foreignkey')
        batch_op.drop_constraint('fk_claim_entities_claim_id', type_='foreignkey')

    with op.batch_alter_table('claims', schema=None) as batch_op:
        batch_op.drop_constraint('fk_claims_document_id', type_='foreignkey')
        batch_op.drop_constraint('fk_claims_chunk_id', type_='foreignkey')

    with op.batch_alter_table('entity_aliases', schema=None) as batch_op:
        batch_op.drop_constraint('fk_entity_aliases_entity_id', type_='foreignkey')

    with op.batch_alter_table('chunks', schema=None) as batch_op:
        batch_op.drop_constraint('fk_chunks_document_id', type_='foreignkey')
