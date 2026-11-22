"""initial schema

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("income", "expense", name="categorykind", native_enum=False, length=10),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name"),
    )
    op.create_index(op.f("ix_categories_user_id"), "categories", ["user_id"], unique=False)
    op.create_table(
        "budgets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("limit_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.CheckConstraint("extract(day from month) = 1", name="month_is_first_day"),
        sa.CheckConstraint("limit_amount > 0", name="limit_positive"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("category_id", "month"),
    )
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.CheckConstraint("amount > 0", name="amount_positive"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_transactions_category_id"), "transactions", ["category_id"], unique=False
    )
    op.create_index(
        op.f("ix_transactions_occurred_on"), "transactions", ["occurred_on"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_transactions_occurred_on"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_category_id"), table_name="transactions")
    op.drop_table("transactions")
    op.drop_table("budgets")
    op.drop_index(op.f("ix_categories_user_id"), table_name="categories")
    op.drop_table("categories")
    op.drop_table("users")
