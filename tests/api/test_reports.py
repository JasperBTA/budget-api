import pytest
from fastapi.testclient import TestClient


def category(client: TestClient, headers: dict[str, str], name: str, kind: str) -> int:
    response = client.post("/categories", json={"name": name, "kind": kind}, headers=headers)
    assert response.status_code == 201, response.text
    category_id: int = response.json()["id"]
    return category_id


def spend(
    client: TestClient, headers: dict[str, str], category_id: int, amount: str, day: str
) -> None:
    response = client.post(
        "/transactions",
        json={"category_id": category_id, "amount": amount, "occurred_on": day},
        headers=headers,
    )
    assert response.status_code == 201, response.text


def test_monthly_report(client: TestClient, alice: dict[str, str], bob: dict[str, str]) -> None:
    salary = category(client, alice, "Salary", "income")
    food = category(client, alice, "Food", "expense")
    fun = category(client, alice, "Fun", "expense")
    spend(client, alice, salary, "5000.00", "2026-11-01")
    spend(client, alice, food, "300.10", "2026-11-03")
    spend(client, alice, food, "250.00", "2026-11-20")
    spend(client, alice, food, "999.00", "2026-12-01")  # other month, must not count
    spend(client, alice, fun, "80.00", "2026-11-05")
    client.put(f"/budgets/{food}/2026-11", json={"limit": "500.00"}, headers=alice)
    client.put(f"/budgets/{fun}/2026-11", json={"limit": "100.00"}, headers=alice)
    # Bob's data must never leak into Alice's report.
    spend(client, bob, category(client, bob, "Food", "expense"), "1.00", "2026-11-03")

    report = client.get("/reports/monthly", params={"month": "2026-11"}, headers=alice).json()

    assert (report["income"], report["expenses"], report["balance"]) == (
        "5000.00",
        "630.10",
        "4369.90",
    )
    lines = {line["name"]: line for line in report["lines"]}
    assert lines["Food"]["total"] == "550.10"
    assert lines["Food"]["remaining"] == "-50.10"
    assert lines["Food"]["over_budget"] is True
    assert lines["Fun"]["over_budget"] is False
    assert lines["Salary"]["limit"] is None


def test_budget_put_is_idempotent_upsert(client: TestClient, alice: dict[str, str]) -> None:
    food = category(client, alice, "Food", "expense")
    client.put(f"/budgets/{food}/2026-11", json={"limit": "500.00"}, headers=alice)
    response = client.put(f"/budgets/{food}/2026-11", json={"limit": "650.00"}, headers=alice)
    assert response.status_code == 200
    assert response.json() == {"category_id": food, "month": "2026-11-01", "limit": "650.00"}


def test_budget_on_income_category_rejected(client: TestClient, alice: dict[str, str]) -> None:
    salary = category(client, alice, "Salary", "income")
    response = client.put(f"/budgets/{salary}/2026-11", json={"limit": "1.00"}, headers=alice)
    assert response.status_code == 422
    assert response.json() == {"detail": "budgets apply only to expense categories"}


def test_budget_on_other_users_category_is_404(
    client: TestClient, alice: dict[str, str], bob: dict[str, str]
) -> None:
    food = category(client, alice, "Food", "expense")
    response = client.put(f"/budgets/{food}/2026-11", json={"limit": "1.00"}, headers=bob)
    assert response.status_code == 404


@pytest.mark.parametrize(
    ("month", "limit"), [("2026-11", "0"), ("2026-13", "1.00"), ("9999-12", "1.00")]
)
def test_invalid_budget_input_is_422(
    client: TestClient, alice: dict[str, str], month: str, limit: str
) -> None:
    food = category(client, alice, "Food", "expense")
    response = client.put(f"/budgets/{food}/{month}", json={"limit": limit}, headers=alice)
    assert response.status_code == 422


def test_report_for_year_9999_is_422_not_500(client: TestClient, alice: dict[str, str]) -> None:
    response = client.get("/reports/monthly", params={"month": "9999-12"}, headers=alice)
    assert response.status_code == 422


def test_empty_month_amounts_keep_two_decimals(client: TestClient, alice: dict[str, str]) -> None:
    report = client.get("/reports/monthly", params={"month": "2026-11"}, headers=alice).json()
    assert (report["income"], report["expenses"], report["balance"]) == ("0.00", "0.00", "0.00")
