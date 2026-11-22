from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from budget.errors import ConflictError
from budget.models import User
from budget.security import DUMMY_HASH, hash_password, verify_password


def register(session: Session, email: str, password: str) -> User:
    user = User(email=email.lower(), password_hash=hash_password(password))
    session.add(user)
    try:
        session.commit()
    except IntegrityError:  # unique(email) is the source of truth, also under concurrent signups
        session.rollback()
        raise ConflictError("email already registered") from None
    return user


def authenticate(session: Session, email: str, password: str) -> User | None:
    user = session.scalar(select(User).where(User.email == email.lower()))
    password_hash = user.password_hash if user else DUMMY_HASH
    if not verify_password(password, password_hash) or user is None:
        return None
    return user


def get(session: Session, user_id: int) -> User | None:
    return session.get(User, user_id)
