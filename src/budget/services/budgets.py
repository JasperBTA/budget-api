from datetime import date
from decimal import Decimal

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from budget.domain.categories import CategoryKind
from budget.errors import BusinessRuleError, NotFoundError
from budget.models import Budget
from budget.services import categories


def set_limit(
    session: Session, user_id: int, category_id: int, month: date, limit: Decimal
) -> Budget:
    """Create or replace the monthly limit for an expense category (idempotent)."""
    category = categories.get_owned(session, user_id, category_id)
    if category.kind is not CategoryKind.EXPENSE:
        raise BusinessRuleError("budgets apply only to expense categories")
    # Atomic upsert: no read-then-write race between two concurrent PUTs.
    upsert = (
        insert(Budget)
        .values(category_id=category_id, month=month, limit_amount=limit)
        .on_conflict_do_update(
            index_elements=[Budget.category_id, Budget.month], set_={"limit_amount": limit}
        )
        .returning(Budget)
    )
    try:
        budget = session.scalars(upsert).one()
        session.commit()
    except IntegrityError:  # category deleted between the ownership check and the upsert
        session.rollback()
        raise NotFoundError("category not found") from None
    return budget
