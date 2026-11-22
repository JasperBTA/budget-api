from fastapi import APIRouter, status

from budget.api.deps import CurrentUser
from budget.db import SessionDep
from budget.schemas import CategoryCreate, CategoryOut, Id
from budget.services import categories

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("")
def list_categories(user: CurrentUser, session: SessionDep) -> list[CategoryOut]:
    return [CategoryOut.model_validate(c) for c in categories.list_for_user(session, user.id)]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_category(body: CategoryCreate, user: CurrentUser, session: SessionDep) -> CategoryOut:
    return CategoryOut.model_validate(categories.create(session, user.id, body.name, body.kind))


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: Id, user: CurrentUser, session: SessionDep) -> None:
    categories.delete(session, user.id, category_id)
