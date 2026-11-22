import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def food(client: TestClient, alice: dict[str, str]) -> int:
    response = client.post("/categories", json={"name": "Food", "kind": "expense"}, headers=alice)
    category_id: int = response.json()["id"]
    return category_id


def add(
    client: TestClient, headers: dict[str, str], category_id: int, amount: str, day: str
) -> int:
    response = client.post(
        "/transactions",
        json={"category_id": category_id, "amount": amount, "occurred_on": day},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    transaction_id: int = response.json()["id"]
    return transaction_id


def test_create_returns_kind_and_exact_amount(
    client: TestClient, alice: dict[str, str], food: int
) -> None:
    add(client, alice, food, "12.50", "2026-11-02")
    [transaction] = client.get("/transactions", headers=alice).json()
    assert transaction["amount"] == "12.50"
    assert transaction["kind"] == "expense"


@pytest.mark.parametrize("amount", ["0", "-5.00", "1.005", "10000000000.00"])
def test_invalid_amount_rejected(
    client: TestClient, alice: dict[str, str], food: int, amount: str
) -> None:
    response = client.post(
        "/transactions",
        json={"category_id": food, "amount": amount, "occurred_on": "2026-11-02"},
        headers=alice,
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "amount"]


@pytest.mark.parametrize(
    ("sent", "returned"), [("12.5", "12.50"), ("7", "7.00"), ("1E+2", "100.00")]
)
def test_amount_is_returned_with_two_decimals_on_create(
    client: TestClient, alice: dict[str, str], food: int, sent: str, returned: str
) -> None:
    response = client.post(
        "/transactions",
        json={"category_id": food, "amount": sent, "occurred_on": "2026-11-02"},
        headers=alice,
    )
    assert response.json()["amount"] == returned


def test_filter_by_month_and_newest_first(
    client: TestClient, alice: dict[str, str], food: int
) -> None:
    add(client, alice, food, "1.00", "2026-10-31")
    add(client, alice, food, "2.00", "2026-11-01")
    add(client, alice, food, "3.00", "2026-11-30")
    add(client, alice, food, "4.00", "2026-12-01")
    found = client.get("/transactions", params={"month": "2026-11"}, headers=alice).json()
    assert [t["amount"] for t in found] == ["3.00", "2.00"]


@pytest.mark.parametrize(
    "params",
    [{"month": "2026-13"}, {"month": "9999-12"}, {"limit": 0}, {"limit": 101}, {"offset": 10**19}],
)
def test_invalid_query_params_are_422(
    client: TestClient, alice: dict[str, str], params: dict[str, object]
) -> None:
    assert client.get("/transactions", params=params, headers=alice).status_code == 422


def test_pagination(client: TestClient, alice: dict[str, str], food: int) -> None:
    for day in range(1, 6):
        add(client, alice, food, f"{day}.00", f"2026-11-0{day}")
    page = client.get("/transactions", params={"limit": 2, "offset": 2}, headers=alice).json()
    assert [t["amount"] for t in page] == ["3.00", "2.00"]


def test_users_are_isolated(
    client: TestClient, alice: dict[str, str], bob: dict[str, str], food: int
) -> None:
    transaction_id = add(client, alice, food, "10.00", "2026-11-02")

    assert client.get("/transactions", headers=bob).json() == []
    by_category = client.get("/transactions", params={"category_id": food}, headers=bob)
    assert by_category.json() == []
    assert client.delete(f"/transactions/{transaction_id}", headers=bob).status_code == 404
    other = client.post(
        "/transactions",
        json={"category_id": food, "amount": "1.00", "occurred_on": "2026-11-02"},
        headers=bob,
    )
    assert other.status_code == 404
    assert other.json() == {"detail": "category not found"}


def test_delete(client: TestClient, alice: dict[str, str], food: int) -> None:
    transaction_id = add(client, alice, food, "10.00", "2026-11-02")
    assert client.delete(f"/transactions/{transaction_id}", headers=alice).status_code == 204
    assert client.get("/transactions", headers=alice).json() == []
