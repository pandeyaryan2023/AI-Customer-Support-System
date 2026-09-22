"""add businesses (multi-tenancy)

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-22 18:00:00

Every row that existed before multi-tenancy is kept and moved into one business,
"Default business" (code "default"). Nothing is deleted. On an empty database no
business is created.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0006'
down_revision: Union[str, Sequence[str], None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OWNED_TABLES = ("users", "categories", "tickets", "documents")
INDEXED_TABLES = ("users", "tickets", "documents")  # categories: its unique (business_id, name) is the index


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('businesses',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('slug', sa.String(length=50), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_businesses_slug'), 'businesses', ['slug'], unique=True)

    # Existing data belongs to one business. Create it only if there is data to hold.
    conn = op.get_bind()
    has_data = any(conn.execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first() for table in OWNED_TABLES)
    default_id = None
    if has_data:
        default_id = conn.execute(sa.text(
            "INSERT INTO businesses (name, slug, is_active, created_at) "
            "VALUES ('Default business', 'default', :active, CURRENT_TIMESTAMP) RETURNING id"),
            {"active": True}).scalar()

    for table in OWNED_TABLES:
        # Add as nullable, fill in, then require it: existing rows are never rejected or lost.
        op.add_column(table, sa.Column('business_id', sa.Integer(), nullable=True))
        if default_id is not None:
            conn.execute(sa.text(f"UPDATE {table} SET business_id = :business"), {"business": default_id})
        op.alter_column(table, 'business_id', existing_type=sa.Integer(), nullable=False)
        op.create_foreign_key(f'fk_{table}_business_id', table, 'businesses', ['business_id'], ['id'])
    for table in INDEXED_TABLES:
        op.create_index(op.f(f'ix_{table}_business_id'), table, ['business_id'], unique=False)

    # Category names: unique per business instead of across the whole system.
    op.drop_constraint('categories_name_key', 'categories', type_='unique')
    op.create_unique_constraint('uq_categories_business_name', 'categories', ['business_id', 'name'])


def downgrade() -> None:
    """Downgrade schema.

    Going back to one business needs category names to be unique again: this fails if two
    businesses have a category with the same name. Rename one of them first.
    """
    op.drop_constraint('uq_categories_business_name', 'categories', type_='unique')
    op.create_unique_constraint('categories_name_key', 'categories', ['name'])
    for table in INDEXED_TABLES:
        op.drop_index(op.f(f'ix_{table}_business_id'), table_name=table)
    for table in OWNED_TABLES:
        op.drop_constraint(f'fk_{table}_business_id', table, type_='foreignkey')
        op.drop_column(table, 'business_id')
    op.drop_index(op.f('ix_businesses_slug'), table_name='businesses')
    op.drop_table('businesses')
