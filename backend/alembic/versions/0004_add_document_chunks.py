"""add document chunks and index status

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-22 14:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '0004'
down_revision: Union[str, Sequence[str], None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Existing documents start as NOT_INDEXED and can be indexed from the admin screen.
    op.add_column('documents', sa.Column(
        'index_status',
        sa.Enum('NOT_INDEXED', 'INDEXED', 'FAILED', name='indexstatus', native_enum=False, length=20),
        server_default='NOT_INDEXED', nullable=False))
    op.add_column('documents', sa.Column('index_error', sa.String(length=300), nullable=True))
    op.add_column('documents', sa.Column('chunk_count', sa.Integer(), nullable=True))

    op.create_table('document_chunks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('document_id', sa.Integer(), nullable=False),
    sa.Column('chunk_index', sa.Integer(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('word_count', sa.Integer(), nullable=False),
    sa.Column('embedding', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('embedding_model', sa.String(length=100), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    # Deleting a document deletes its chunks, even if done directly in the database.
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    # One chunk 0, one chunk 1... per document: duplicates are refused by the database.
    sa.UniqueConstraint('document_id', 'chunk_index')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('document_chunks')
    op.drop_column('documents', 'chunk_count')
    op.drop_column('documents', 'index_error')
    op.drop_column('documents', 'index_status')
