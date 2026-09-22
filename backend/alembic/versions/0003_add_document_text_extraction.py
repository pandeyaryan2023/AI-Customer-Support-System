"""add document text extraction

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-22 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, Sequence[str], None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default: documents uploaded before this migration get PENDING, so a NOT NULL
    # column can be added to a table that already has rows. They can be extracted later.
    op.add_column('documents', sa.Column(
        'status',
        sa.Enum('PENDING', 'EXTRACTED', 'FAILED', name='documentstatus', native_enum=False, length=20),
        server_default='PENDING', nullable=False))
    op.add_column('documents', sa.Column('extracted_text', sa.Text(), nullable=True))
    op.add_column('documents', sa.Column('page_count', sa.Integer(), nullable=True))
    op.add_column('documents', sa.Column('char_count', sa.Integer(), nullable=True))
    op.add_column('documents', sa.Column('extraction_error', sa.String(length=300), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('documents', 'extraction_error')
    op.drop_column('documents', 'char_count')
    op.drop_column('documents', 'page_count')
    op.drop_column('documents', 'extracted_text')
    op.drop_column('documents', 'status')
