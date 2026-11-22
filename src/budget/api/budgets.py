from fastapi import APIRouter

from budget.api.deps import CurrentUser
from budget.db import SessionDep
from budget.schemas import BudgetOut, BudgetSet, Id, Month
from budget.services import budgets

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.put("/{category_id}/{month}")
def set_budget(
    category_id: Id, month: Month, body: BudgetSet, user: CurrentUser, session: SessionDep
) -> BudgetOut:
    budget = budgets.set_limit(session, user.id, category_id, month, body.limit)
    return BudgetOut.model_validate(budget)
