import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from budget.models import Budget


def test_create_and_list(client: TestClient, alice: dict[str, str]) -> None:
    client.post("/categories", json={"name": "Rent", "kind": "expense"}, headers=alice)
    client.post("/categories", json={"name": "Salary", "kind": "income"}, headers=alice)
    names = [c["name"] for c in client.get("/categories", headers=alice).json()]
    assert names == ["Rent", "Salary"]


def test_duplicate_name_conflicts(client: TestClient, alice: dict[str, str]) -> None:
    body = {"name": "Rent", "kind": "expense"}
    client.post("/categories", json=body, headers=alice)
    response = client.post("/categories", json=body, headers=alice)
    assert response.status_code == 409
    assert response.json() == {"detail": "category with this name already exists"}


def test_same_name_allowed_for_different_users(
    client: TestClient, alice: dict[str, str], bob: dict[str, str]
) -> None:
    body = {"name": "Rent", "kind": "expense"}
    assert client.post("/categories", json=body, headers=alice).status_code == 201
    assert client.post("/categories", json=body, headers=bob).status_code == 201


def test_cannot_delete_category_with_transactions(
    client: TestClient, alice: dict[str, str]
) -> None:
    category = client.post("/categories", json={"name": "Food", "kind": "expense"}, headers=alice)
    category_id = category.json()["id"]
    client.post(
        "/transactions",
        json={"category_id": category_id, "amount": "10.00", "occurred_on": "2026-11-02"},
        headers=alice,
    )
    response = client.delete(f"/categories/{category_id}", headers=alice)
    assert response.status_code == 409
    assert response.json() == {"detail": "category has transactions"}


def test_other_users_category_is_not_found(
    client: TestClient, alice: dict[str, str], bob: dict[str, str]
) -> None:
    category = client.post("/categories", json={"name": "Food", "kind": "expense"}, headers=alice)
    assert client.delete(f"/categories/{category.json()['id']}", headers=bob).status_code == 404


def test_list_shows_only_own_categories(
    client: TestClient, alice: dict[str, str], bob: dict[str, str]
) -> None:
    client.post("/categories", json={"name": "Rent", "kind": "expense"}, headers=alice)
    assert client.get("/categories", headers=bob).json() == []


def test_delete_empty_category_removes_its_budgets(
    client: TestClient, alice: dict[str, str], session: Session
) -> None:
    category = client.post("/categories", json={"name": "Fun", "kind": "expense"}, headers=alice)
    category_id = category.json()["id"]
    client.put(f"/budgets/{category_id}/2026-11", json={"limit": "50.00"}, headers=alice)

    assert client.delete(f"/categories/{category_id}", headers=alice).status_code == 204
    assert client.get("/categories", headers=alice).json() == []
    assert session.scalars(select(Budget).where(Budget.category_id == category_id)).all() == []


def test_id_outside_int4_is_422_not_500(client: TestClient, alice: dict[str, str]) -> None:
    assert client.delete("/categories/99999999999", headers=alice).status_code == 422


def test_database_rejects_unknown_kind(session: Session, alice: dict[str, str]) -> None:
    # Rule 6: the DB enforces the invariant even if application code is bypassed.
    with pytest.raises(IntegrityError):
        session.execute(
            text(
                "INSERT INTO categories (user_id, name, kind) "
                "SELECT id, 'Bad', 'gift' FROM users LIMIT 1"
            )
        )
