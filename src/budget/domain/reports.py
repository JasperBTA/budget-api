"""Pure report logic: no database, no HTTP. Fed by services.reports."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from budget.domain.categories import CategoryKind

ZERO = Decimal("0.00")


@dataclass(frozen=True, slots=True)
class CategoryLine:
    category_id: int
    name: str
    kind: CategoryKind
    total: Decimal
    limit: Decimal | None = None

    @property
    def remaining(self) -> Decimal | None:
        return None if self.limit is None else self.limit - self.total

    @property
    def over_budget(self) -> bool:
        return self.limit is not None and self.total > self.limit


@dataclass(frozen=True, slots=True)
class MonthlyReport:
    month: date
    lines: tuple[CategoryLine, ...]

    def _sum(self, kind: CategoryKind) -> Decimal:
        return sum((line.total for line in self.lines if line.kind is kind), ZERO)

    @property
    def income(self) -> Decimal:
        return self._sum(CategoryKind.INCOME)

    @property
    def expenses(self) -> Decimal:
        return self._sum(CategoryKind.EXPENSE)

    @property
    def balance(self) -> Decimal:
        return self.income - self.expenses

    @property
    def average_expense(self) -> float:
        expense_lines = [line for line in self.lines if line.kind is CategoryKind.EXPENSE]
        return float(self.expenses) / len(expense_lines) if expense_lines else 0.0
