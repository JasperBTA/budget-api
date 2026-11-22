from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from budget.domain.categories import CategoryKind
from budget.errors import ConflictError, NotFoundError
from budget.models import Category


def get_owned(session: Session, user_id: int, category_id: int) -> Category:
    """Fetch a category the user owns. Another user's category is reported as 404, not 403."""
    category = session.get(Category, category_id)
    if category is None or category.user_id != user_id:
        raise NotFoundError("category not found")
    return category


def list_for_user(session: Session, user_id: int) -> Sequence[Category]:
    query = select(Category).where(Category.user_id == user_id).order_by(Category.name)
    return session.scalars(query).all()


def create(session: Session, user_id: int, name: str, kind: CategoryKind) -> Category:
    category = Category(user_id=user_id, name=name, kind=kind)
    session.add(category)
    try:
        session.commit()
    except IntegrityError:  # unique(user_id, name)
        session.rollback()
        raise ConflictError("category with this name already exists") from None
    return category


def delete(session: Session, user_id: int, category_id: int) -> None:
    """Budgets go with the category (planning data); transactions block it (FK RESTRICT)."""
    session.delete(get_owned(session, user_id, category_id))
    try:
        session.commit()
    except IntegrityError:  # FK RESTRICT from transactions, also when one is added concurrently
        session.rollback()
        raise ConflictError("category has transactions") from None
