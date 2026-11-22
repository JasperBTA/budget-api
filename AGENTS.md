# AGENTS.md

Rules for any coding agent (and human) working in this repository. They are not suggestions:
a change that breaks one of them is not done. When a rule and a request conflict, stop and ask.

## Project

Personal budget REST API: users own categories (income/expense), record transactions, set monthly
limits per expense category and read monthly reports.

Stack: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x (sync), Alembic, PostgreSQL 17, pytest,
ruff, mypy (strict), uv.

## Commands

```bash
uv sync                                   # install
docker compose up -d db                   # Postgres for dev + tests (creates budget_test)
uv run alembic upgrade head               # migrate dev DB
uv run uvicorn budget.main:app --reload   # run (needs JWT_SECRET, see .env.example)

uv run ruff check . && uv run ruff format --check . && uv run mypy src tests scripts && uv run pytest
```

The last line is the definition of "it works". CI runs exactly that.

## Architecture

```
src/budget/
  api/        HTTP: routers, auth dependency. Thin.
  services/   Use cases + business rules. Talks to the DB through a SQLAlchemy Session.
  domain/     Pure Python: calculations, value rules. No I/O, no framework imports.
  models.py   SQLAlchemy tables.        schemas.py  Pydantic request/response models.
  errors.py   Domain exceptions.        main.py     App, routers, error -> HTTP mapping.
scripts/
  ai_review.py  Gemini PR review run by CI (.github/workflows/ai-review.yml). Not part of the
                app: it never imports `budget`, and the app never imports it.
```

Dependency direction is one way: `api -> services -> domain`. Never the reverse.

| Layer       | May import                                             | Must not                            |
|-------------|--------------------------------------------------------|-------------------------------------|
| `domain/`   | stdlib, other `domain/` modules                        | import SQLAlchemy, FastAPI, Pydantic |
| `services/` | `domain`, `models`, `errors`, `security`               | import FastAPI, `schemas`, `HTTPException` |
| `api/`      | `services`, `schemas`, `deps`, `db`, `security`, `models` (type hints only) | run SQL (`select`, `session.*`) |

- **Routers are thin**: validate input (Pydantic), call one service function, wrap the result in a
  response schema. No business logic, no queries.
- **Services take plain values** (`user_id: int`, `Decimal`, `date`), not Pydantic models, so they
  can be called from a CLI, a job or a test without HTTP.
- **No repository layer.** The `Session` already is the unit of work and repository. Add an
  abstraction only when there is a second implementation to justify it.
- **Pure logic goes to `domain/`** and gets unit tests without a database.

## Business rules (do not break)

1. **Money is `Decimal`, never `float`.** DB column `Numeric(12, 2)`; API accepts and returns money
   as a string with 2 decimals (`"12.50"`). Use `Decimal("0.00")`, never `Decimal(0.1)`.
2. **Amounts are always positive.** Income vs expense comes from the category's `kind`, so the sign
   cannot contradict the category.
3. **Ownership goes through the category.** Every query on transactions/budgets joins or checks
   `Category.user_id`. Another user's resource returns **404, not 403** (do not reveal it exists).
4. **Budgets apply only to expense categories**, one per `(category, month)`; `month` is stored as
   the first day of the month. `PUT` is an idempotent upsert.
5. **A category with transactions cannot be deleted** (409, enforced by FK `RESTRICT`).
   Transactions are financial records and are never removed by a cascade. Budgets are planning
   data: deleting an (empty) category removes its budgets on purpose (`CASCADE`).
6. **The database is the source of truth for invariants.** Uniqueness and value rules live in
   constraints (`UNIQUE`, `CHECK`); services catch `IntegrityError` or use atomic upserts instead of
   check-then-write, which races under concurrent requests.

## Code rules

- Full type hints; `mypy --strict` passes with no `type: ignore` unless a comment explains why.
- `Annotated[...]` dependencies (`SessionDep`, `CurrentUser`) instead of `= Depends()` defaults.
- Pydantic only at the HTTP boundary (`schemas.py`). Responses always go through a response
  schema: never return ORM objects or dicts that may leak fields like `password_hash`.
- Errors: services raise `NotFoundError` / `ConflictError` / `BusinessRuleError`; `main.py` maps them
  to 404 / 409 / 422. Do not raise `HTTPException` outside `api/`.
- Dates are `date` (no time zone needed for a calendar month). Timestamps, if added, are aware UTC
  (`datetime.now(UTC)`); ruff's `DTZ` rules enforce it.
- Configuration only through `budget.config.settings` (env vars). No secrets in code; required
  secrets have no default.
- Comments explain *why*, not *what*. No commented-out code, no TODOs without an issue.
- Add a dependency only when it replaces substantial code; never for a few lines.

## Database and migrations

- Every model change ships with an Alembic migration in the same commit:
  `uv run alembic revision --autogenerate --rev-id 0003 -m "<what>"` (next free number), then
  **read and fix** the generated file
  (autogenerate misses renames, data migrations and some constraints).
- Revision ids are sequential and readable (`0002_<slug>.py`, `revision = "0002"`), hence `--rev-id`.
- Autogenerate does not detect `CHECK` constraints: add them by hand (see `0002`).
- Migrations must downgrade cleanly. The test suite runs `downgrade base` + `upgrade head`, so a
  broken migration fails CI.
- Never edit a migration that has been merged to `main`; add a new one.

## API conventions

- Plural nouns: `/categories`, `/transactions`; nesting only for natural keys
  (`/budgets/{category_id}/{month}`).
- `201` on create, `204` on delete, `200` otherwise. Errors use FastAPI's `{"detail": "..."}` shape.
- Months in URLs and queries are `YYYY-MM` (the `Month` type in `schemas.py`).
- Lists that grow without bound (transactions) are paginated with `limit` (1–100, default 50) and
  `offset`, with a deterministic order. Small per-user lists (categories) are not.
- Path and body ids use the `Id` type (Postgres `INTEGER` range), so bad ids are 422, never 500.
- Any user input must end in a 4xx. A 500 reachable from input is a bug; add a test for it.

## Testing

- Every business rule above has at least one test. A bug fix starts with a failing test.
- Rules enforced by the database (rule 6) get a test that bypasses the app and hits the DB directly.
- `tests/unit/`: pure logic without a DB: `domain/` (rounding, month rollover, limit boundaries)
  and `scripts/` (diff parsing, the review's skip paths, with `gh` and Gemini faked).
- `tests/api/`: through HTTP with `TestClient` against **real PostgreSQL** (`budget_test`), never
  SQLite: constraints and `Numeric` behave differently there.
- Each test runs in a rolled-back transaction (see `tests/conftest.py`); tests are independent and
  order-free. Use the `alice` / `bob` fixtures; every new endpoint gets a user-isolation test.
- Assert on exact values (`"12.50"`), not just status codes.

## Workflow for an agent

1. Read the files you will touch and their tests before editing.
2. Make the smallest change that fully solves the task; do not refactor unrelated code.
3. Update tests, migrations and this file if a rule changes.
4. Run the full check command. Report failures as they are; do not skip or `xfail` tests to pass.
5. Commits: small, English, imperative (`Add monthly budget upsert`), one logical change each.
