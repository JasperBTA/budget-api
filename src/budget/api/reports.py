from typing import Annotated

from fastapi import APIRouter, Query

from budget.api.deps import CurrentUser
from budget.db import SessionDep
from budget.schemas import Month, MonthlyReportOut
from budget.services import reports

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/monthly")
def monthly_report(
    month: Annotated[Month, Query(description="YYYY-MM")], user: CurrentUser, session: SessionDep
) -> MonthlyReportOut:
    return MonthlyReportOut.model_validate(reports.monthly(session, user.id, month))
