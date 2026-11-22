from datetime import UTC, datetime, timedelta

import jwt
from fastapi.testclient import TestClient

from budget.config import settings


def test_register_and_login(client: TestClient) -> None:
    response = client.post(
        "/auth/register", json={"email": "Ann@Example.com", "password": "long-enough"}
    )
    assert response.status_code == 201
    assert response.json()["email"] == "ann@example.com"

    token = client.post(
        "/auth/token", data={"username": "ANN@example.com", "password": "long-enough"}
    )
    assert token.status_code == 200
    assert token.json()["token_type"] == "bearer"


def test_duplicate_email_conflicts(client: TestClient) -> None:
    body = {"email": "ann@example.com", "password": "long-enough"}
    client.post("/auth/register", json=body)
    response = client.post("/auth/register", json=body)
    assert response.status_code == 409
    assert response.json() == {"detail": "email already registered"}


def test_wrong_password_rejected(client: TestClient) -> None:
    client.post("/auth/register", json={"email": "ann@example.com", "password": "long-enough"})
    response = client.post("/auth/token", data={"username": "ann@example.com", "password": "nope"})
    assert response.status_code == 401


def test_password_over_bcrypt_limit_is_422_not_500(client: TestClient) -> None:
    response = client.post("/auth/register", json={"email": "a@example.com", "password": "ż" * 40})
    assert response.status_code == 422


def test_protected_endpoint_requires_valid_token(client: TestClient) -> None:
    assert client.get("/categories").status_code == 401
    bad = {"Authorization": "Bearer not-a-jwt"}
    assert client.get("/categories", headers=bad).status_code == 401


def test_login_with_overlong_password_is_401_not_500(client: TestClient) -> None:
    client.post("/auth/register", json={"email": "ann@example.com", "password": "long-enough"})
    response = client.post(
        "/auth/token", data={"username": "ann@example.com", "password": "x" * 80}
    )
    assert response.status_code == 401


def test_expired_token_rejected(client: TestClient) -> None:
    expired = jwt.encode(
        {"sub": "1", "exp": datetime.now(UTC) - timedelta(minutes=1)}, settings.jwt_secret, "HS256"
    )
    response = client.get("/categories", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401
