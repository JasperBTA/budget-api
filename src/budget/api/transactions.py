from typing import Annotated

from fastapi import APIRouter, Query, status

from budget.api.deps import CurrentUser
from budget.db import SessionDep
from budget.schemas import Id, Month, TransactionCreate, TransactionOut
from budget.services import transactions

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("")
def list_transactions(
    user: CurrentUser,
    session: SessionDep,
    month: Annotated[Month | None, Query(description="YYYY-MM")] = None,
    category_id: Id | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=2**31 - 1)] = 0,
) -> list[TransactionOut]:
    found = transactions.list_for_user(
        session, user.id, month=month, category_id=category_id, limit=limit, offset=offset
    )
    return [TransactionOut.model_validate(t) for t in found]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_transaction(
    body: TransactionCreate, user: CurrentUser, session: SessionDep
) -> TransactionOut:
    created = transactions.create(
        session, user.id, body.category_id, body.amount, body.occurred_on, body.note
    )
    return TransactionOut.model_validate(created)


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(transaction_id: Id, user: CurrentUser, session: SessionDep) -> None:
    transactions.delete(session, user.id, transaction_id)
