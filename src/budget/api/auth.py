from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from budget.db import SessionDep
from budget.schemas import Token, UserCreate, UserOut
from budget.security import create_access_token
from budget.services import users

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: UserCreate, session: SessionDep) -> UserOut:
    return UserOut.model_validate(users.register(session, body.email, body.password))


@router.post("/token")
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], session: SessionDep) -> Token:
    user = users.authenticate(session, form.username, form.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "incorrect email or password")
    return Token(access_token=create_access_token(user.id))
