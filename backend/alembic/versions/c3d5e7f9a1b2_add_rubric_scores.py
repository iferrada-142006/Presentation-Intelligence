"""add rubric scores

Revision ID: c3d5e7f9a1b2
Revises: b2e4f6a8c0d1
Create Date: 2026-10-04 14:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'c3d5e7f9a1b2'
down_revision: Union[str, None] = 'b2e4f6a8c0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'rubric_scores',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('presentation_id', sa.Integer(), nullable=False),
        sa.Column('dimension', sa.String(length=50), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('level', sa.Integer(), nullable=False),
        sa.Column('level_label', sa.String(length=50), nullable=False),
        sa.Column('primary_metric', sa.String(length=100), nullable=True),
        sa.Column('primary_value', sa.Float(), nullable=True),
        sa.Column('evidence', sa.Text(), nullable=True),
        sa.Column('rubric_version', sa.String(length=20), nullable=True),
        sa.ForeignKeyConstraint(['presentation_id'], ['presentations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_rubric_scores_id'), 'rubric_scores', ['id'], unique=False)
    op.create_index('ix_rubric_scores_presentation_id', 'rubric_scores', ['presentation_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_rubric_scores_presentation_id', table_name='rubric_scores')
    op.drop_index(op.f('ix_rubric_scores_id'), table_name='rubric_scores')
    op.drop_table('rubric_scores')
