import os
from collections.abc import Iterator
from pathlib import Path

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://budget:budget@localhost:5432/budget_test"
)
os.environ.setdefault("JWT_SECRET", "test-secret-at-least-32-bytes-long")

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from budget.db import engine, get_session
from budget.main import app

ALEMBIC_INI = Path(__file__).parents[1] / "alembic.ini"


@pytest.fixture(scope="session", autouse=True)
def schema() -> None:
    """Build the schema with the real migrations, so a broken migration fails the suite."""
    config = Config(ALEMBIC_INI)
    config.attributes["configure_logger"] = False
    command.downgrade(config, "base")
    command.upgrade(config, "head")


@pytest.fixture
def session() -> Iterator[Session]:
    """Each test runs inside a transaction that is rolled back; commits become savepoints."""
    with engine.connect() as connection:
        transaction = connection.begin()
        session = Session(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        yield session
        session.close()
        transaction.rollback()


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def login(client: TestClient, email: str, password: str = "correct-horse") -> dict[str, str]:
    client.post("/auth/register", json={"email": email, "password": password})
    response = client.post("/auth/token", data={"username": email, "password": password})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def alice(client: TestClient) -> dict[str, str]:
    return login(client, "alice@example.com")


@pytest.fixture
def bob(client: TestClient) -> dict[str, str]:
    return login(client, "bob@example.com")
