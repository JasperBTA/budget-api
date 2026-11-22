from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, contains_eager

from budget.domain.months import next_month
from budget.errors import NotFoundError
from budget.models import Category, Transaction
from budget.services import categories


def create(
    session: Session,
    user_id: int,
    category_id: int,
    amount: Decimal,
    occurred_on: date,
    note: str | None,
) -> Transaction:
    category = categories.get_owned(session, user_id, category_id)
    transaction = Transaction(category=category, amount=amount, occurred_on=occurred_on, note=note)
    session.add(transaction)
    try:
        session.commit()
    except IntegrityError:  # category deleted between the ownership check and the insert
        session.rollback()
        raise NotFoundError("category not found") from None
    return transaction


def list_for_user(
    session: Session,
    user_id: int,
    *,
    month: date | None = None,
    category_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> Sequence[Transaction]:
    query = (
        select(Transaction)
        .join(Transaction.category)
        .options(contains_eager(Transaction.category))  # reuse the join, don't add a second one
        .where(Category.user_id == user_id)
        .order_by(Transaction.occurred_on.desc(), Transaction.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if month is not None:
        query = query.where(
            Transaction.occurred_on >= month, Transaction.occurred_on < next_month(month)
        )
    if category_id is not None:
        query = query.where(Transaction.category_id == category_id)
    return session.scalars(query).all()


def delete(session: Session, user_id: int, transaction_id: int) -> None:
    transaction = session.get(Transaction, transaction_id)
    if transaction is None or transaction.category.user_id != user_id:
        raise NotFoundError("transaction not found")
    session.delete(transaction)
    session.commit()
