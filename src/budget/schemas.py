"""Pydantic models for the HTTP boundary only. Services never import this module."""

from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)

from budget.domain.categories import CategoryKind
from budget.domain.months import parse_month

# Money is serialized as a JSON string ("12.50") so clients never round-trip it through a float.
# Quantize so "12.5" or "1E+2" come back as "12.50" / "100.00", same as a later GET.
Money = Annotated[
    Decimal,
    Field(gt=0, max_digits=12, decimal_places=2),
    AfterValidator(lambda d: d.quantize(Decimal("0.01"))),
]
Month = Annotated[date, BeforeValidator(parse_month)]
# Postgres INTEGER range: larger ids would surface as a 500 (DataError) instead of a 422.
Id = Annotated[int, Field(ge=1, le=2**31 - 1)]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def fits_bcrypt(cls, value: str) -> str:
        if len(value.encode()) > 72:
            raise ValueError("password must be at most 72 bytes")
        return value


class UserOut(ORMModel):
    id: int
    email: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    kind: CategoryKind


class CategoryOut(ORMModel):
    id: int
    name: str
    kind: CategoryKind


class TransactionCreate(BaseModel):
    category_id: Id
    amount: Money
    occurred_on: date
    note: str | None = Field(default=None, max_length=200)


class TransactionOut(ORMModel):
    id: int
    category_id: int
    kind: CategoryKind = Field(validation_alias="category_kind")
    amount: Decimal
    occurred_on: date
    note: str | None


class BudgetSet(BaseModel):
    limit: Money


class BudgetOut(ORMModel):
    category_id: int
    month: date
    limit: Decimal = Field(validation_alias="limit_amount")


class CategoryLineOut(ORMModel):
    category_id: int
    name: str
    kind: CategoryKind
    total: Decimal
    limit: Decimal | None
    remaining: Decimal | None
    over_budget: bool


class MonthlyReportOut(ORMModel):
    month: date
    income: Decimal
    expenses: Decimal
    balance: Decimal
    average_expense: float
    lines: list[CategoryLineOut]
