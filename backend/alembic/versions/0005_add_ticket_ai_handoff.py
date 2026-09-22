"""add AI handoff context to tickets

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-22 16:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '0005'
down_revision: Union[str, Sequence[str], None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Both nullable: every existing ticket simply has no AI handoff. No data is changed.
    op.add_column('tickets', sa.Column('handoff_id', sa.String(length=32), nullable=True))
    op.add_column('tickets', sa.Column(
        'ai_handoff', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'),
        nullable=True))
    # One ticket per handoff: a double submit cannot create a second one. A unique index
    # enforces this exactly like a constraint, and can be added to an existing table everywhere.
    op.create_index(op.f('ix_tickets_handoff_id'), 'tickets', ['handoff_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_tickets_handoff_id'), table_name='tickets')
    op.drop_column('tickets', 'ai_handoff')
    op.drop_column('tickets', 'handoff_id')
