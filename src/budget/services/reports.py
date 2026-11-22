from datetime import date

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from budget.domain.months import next_month
from budget.domain.reports import ZERO, CategoryLine, MonthlyReport
from budget.models import Budget, Category, Transaction


def monthly(session: Session, user_id: int, month: date) -> MonthlyReport:
    # Aggregate in SQL (one row per category), compute totals and budget status in the domain.
    totals = (
        select(Transaction.category_id, func.sum(Transaction.amount).label("total"))
        .join(Transaction.category)
        .where(
            Category.user_id == user_id,  # aggregate only this user's rows, not the whole table
            Transaction.occurred_on >= month,
            Transaction.occurred_on < next_month(month),
        )
        .group_by(Transaction.category_id)
        .subquery()
    )
    query = (
        select(Category, totals.c.total, Budget.limit_amount)
        .outerjoin(totals, totals.c.category_id == Category.id)
        .outerjoin(Budget, and_(Budget.category_id == Category.id, Budget.month == month))
        .where(Category.user_id == user_id)
        .order_by(Category.kind, Category.name)
    )
    lines = tuple(
        CategoryLine(
            category_id=category.id,
            name=category.name,
            kind=category.kind,
            total=total or ZERO,
            limit=limit,
        )
        for category, total, limit in session.execute(query)
    )
    return MonthlyReport(month=month, lines=lines)
