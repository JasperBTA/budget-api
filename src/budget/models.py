from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from budget.domain.categories import CategoryKind

MONEY = Numeric(12, 2)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(String(100))


class Category(Base):
    """Ownership root: transactions and budgets belong to a user through their category."""

    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("user_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(50))
    kind: Mapped[CategoryKind] = mapped_column(
        Enum(
            CategoryKind,
            native_enum=False,
            create_constraint=True,
            length=10,
            values_callable=lambda kinds: [k.value for k in kinds],
        )
    )


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (CheckConstraint("amount > 0", name="amount_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), index=True
    )
    # Always positive; income vs expense comes from the category, so the sign can't disagree.
    amount: Mapped[Decimal] = mapped_column(MONEY)
    occurred_on: Mapped[date] = mapped_column(Date, index=True)
    note: Mapped[str | None] = mapped_column(String(200))

    category: Mapped[Category] = relationship(lazy="joined")

    @property
    def category_kind(self) -> CategoryKind:
        return self.category.kind


class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint("category_id", "month"),
        CheckConstraint("limit_amount > 0", name="limit_positive"),
        CheckConstraint("extract(day from month) = 1", name="month_is_first_day"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    month: Mapped[date] = mapped_column(Date)
    limit_amount: Mapped[Decimal] = mapped_column(MONEY)
