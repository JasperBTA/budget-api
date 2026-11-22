import re
from datetime import date

_MONTH = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


def parse_month(value: object) -> object:
    """Turn 'YYYY-MM' into the first day of that month. Other input passes through to pydantic."""
    if isinstance(value, str) and (match := _MONTH.match(value)) and match[1] != "9999":
        # 9999 is excluded because next_month() would overflow date.max
        return date(int(match[1]), int(match[2]), 1)
    if isinstance(value, str):
        raise ValueError("month must be in YYYY-MM format (year < 9999)")
    return value


def next_month(month: date) -> date:
    return date(month.year + month.month // 12, month.month % 12 + 1, 1)
