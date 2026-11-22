from datetime import date
from decimal import Decimal

import pytest

from budget.domain.categories import CategoryKind
from budget.domain.months import next_month, parse_month
from budget.domain.reports import CategoryLine, MonthlyReport

NOV = date(2026, 11, 1)


def line(kind: CategoryKind, total: str, limit: str | None = None) -> CategoryLine:
    return CategoryLine(
        category_id=1,
        name="x",
        kind=kind,
        total=Decimal(total),
        limit=None if limit is None else Decimal(limit),
    )


def test_totals_and_balance() -> None:
    report = MonthlyReport(
        NOV,
        (
            line(CategoryKind.INCOME, "5000.00"),
            line(CategoryKind.EXPENSE, "1200.10"),
            line(CategoryKind.EXPENSE, "0.20"),
        ),
    )
    assert report.income == Decimal("5000.00")
    assert report.expenses == Decimal("1200.30")
    assert report.balance == Decimal("3799.70")


def test_empty_report_is_zero() -> None:
    report = MonthlyReport(NOV, ())
    # str(): Decimal equality ignores scale, but the API must return "0.00"
    assert [str(v) for v in (report.income, report.expenses, report.balance)] == ["0.00"] * 3


@pytest.mark.parametrize(
    ("total", "limit", "remaining", "over"),
    [
        ("99.99", "100.00", Decimal("0.01"), False),
        ("100.00", "100.00", Decimal("0.00"), False),
        ("100.01", "100.00", Decimal("-0.01"), True),
        ("100.01", None, None, False),
    ],
)
def test_budget_status(
    total: str, limit: str | None, remaining: Decimal | None, over: bool
) -> None:
    budget_line = line(CategoryKind.EXPENSE, total, limit)
    assert budget_line.remaining == remaining
    assert budget_line.over_budget is over


@pytest.mark.parametrize(
    ("month", "expected"),
    [(date(2026, 11, 1), date(2026, 12, 1)), (date(2026, 12, 1), date(2027, 1, 1))],
)
def test_next_month_rolls_over_year(month: date, expected: date) -> None:
    assert next_month(month) == expected


def test_parse_month() -> None:
    assert parse_month("2026-02") == date(2026, 2, 1)
    for bad in ("2026-13", "2026-1", "26-01", "2026-01-05", "9999-12"):
        with pytest.raises(ValueError, match="YYYY-MM"):
            parse_month(bad)
