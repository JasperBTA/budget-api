# Budget API

A personal budget REST API built with **FastAPI**, **SQLAlchemy 2.0** and **PostgreSQL**.
Track income and expenses by category, set monthly spending limits and get a monthly report that
flags categories over budget.

The project is small on purpose. The point is the engineering around it: a clear layered
architecture, business rules enforced in both code and database, strict typing, tests against a
real database and explicit [project rules for AI coding agents](AGENTS.md).

## Features

- JWT authentication (OAuth2 password flow, works with the Swagger "Authorize" button)
- Income/expense categories, transactions with filtering and pagination
- Monthly budget per expense category (idempotent `PUT` upsert)
- Monthly report: income, expenses, balance, per-category totals vs. limits
- Full per-user data isolation

## Quick start

```bash
cp .env.example .env    # then set JWT_SECRET: openssl rand -hex 32
docker compose up --build
```

The API refuses to start without a real `JWT_SECRET` (min. 32 chars). There is no fallback key.

Open **http://localhost:8000/docs**, register a user via `POST /auth/register`, click
**Authorize** and try the endpoints.

## Example

```http
GET /reports/monthly?month=2026-11
```

```json
{
  "month": "2026-11-01",
  "income": "5000.00",
  "expenses": "630.10",
  "balance": "4369.90",
  "lines": [
    {"category_id": 2, "name": "Food", "kind": "expense",
     "total": "550.10", "limit": "500.00", "remaining": "-50.10", "over_budget": true}
  ]
}
```

## API

| Method   | Path                              | Description                          |
|----------|-----------------------------------|--------------------------------------|
| `POST`   | `/auth/register`                  | Create account                       |
| `POST`   | `/auth/token`                     | Log in, get a JWT                    |
| `GET`    | `/categories`                     | List your categories                 |
| `POST`   | `/categories`                     | Create category (`income`/`expense`) |
| `DELETE` | `/categories/{id}`                | Delete with its budgets (409 if it has transactions) |
| `GET`    | `/transactions`                   | List; `?month=YYYY-MM&category_id=&limit=&offset=` |
| `POST`   | `/transactions`                   | Record a transaction                 |
| `DELETE` | `/transactions/{id}`              | Delete a transaction                 |
| `PUT`    | `/budgets/{category_id}/{YYYY-MM}`| Set monthly limit                    |
| `GET`    | `/reports/monthly?month=YYYY-MM`  | Monthly report                       |

## Design decisions

- **Layers with one-way dependencies**: `api → services → domain`. Services know nothing about
  HTTP; `domain/` is pure Python and unit-tested without a database.
- **Money is `Decimal` end to end**: `Numeric(12,2)` in Postgres, strings like `"12.50"` in JSON.
  No floats anywhere.
- **Invariants live in the database**: `UNIQUE` and `CHECK` constraints, `IntegrityError` handling
  and an atomic `INSERT … ON CONFLICT` upsert instead of race-prone check-then-write.
- **Amounts are always positive**: income/expense comes from the category, so a sign can never
  contradict it.
- **Every bad input is a 4xx, never a 500**: ids are bounded to the DB integer range, months
  to valid dates, money is quantized to 2 decimals on input.
- **404 instead of 403** for other users' resources, so the API does not reveal what exists.
- **No repository layer**: SQLAlchemy's `Session` already is one; another wrapper would only add
  indirection.

## Development

Requires [uv](https://docs.astral.sh/uv/) and Docker.

```bash
uv sync
docker compose up -d db
cp .env.example .env              # set JWT_SECRET (min. 32 chars): openssl rand -hex 32
uv run alembic upgrade head
uv run uvicorn budget.main:app --reload
```

Checks (same as CI):

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy src tests scripts && uv run pytest
```

Tests run against a real PostgreSQL database (`budget_test`, created on the first start of the
`db` volume; with an older volume run `docker compose down -v` once). The schema is built by the actual
Alembic migrations, and each test runs in a transaction that is rolled back.

## AI review on pull requests

Every pull request gets an advisory review from Gemini (`gemini-4-hydrogen`, falling back to
`gemini-3.5-flash-lite` when it is unavailable, rate-limited or unknown; see
[design 0001](docs/design/0001-gemini-fallback-model.md)), checked against
the rules in [`AGENTS.md`](AGENTS.md) from the base branch. Findings appear as line comments.
The required gate stays CI (ruff, mypy, pytest): if the key is missing, the quota is used up or
the API keeps failing after 3 attempts with backoff on each model, the review is skipped with a
note and never blocks a merge.

Setup for a fork: add a Gemini API key from [Google AI Studio](https://aistudio.google.com) as
the repository secret `GEMINI_API_KEY`. Anyone who can push a branch to the repo can read that
secret from a workflow, so use a free-tier key without billing.
Code: [`scripts/ai_review.py`](scripts/ai_review.py),
[`.github/workflows/ai-review.yml`](.github/workflows/ai-review.yml).

## How this repo is built

The code is written by a coding agent (Claude Code) under rules that machines check, with a
human approving the design, the push and the merge. **Start with
[`docs/pipeline.md`](docs/pipeline.md)**: the path of a change, what enforces each rule, and the
pull requests where the checks caught something.

| What | Where |
| --- | --- |
| Rules every agent and human follows | [`AGENTS.md`](AGENTS.md) (`CLAUDE.md` imports it) |
| Checks while the agent works | [`.claude/settings.json`](.claude/settings.json), [`.claude/hooks/`](.claude/hooks/) |
| Read-only reviewer subagent | [`.claude/agents/reviewer.md`](.claude/agents/reviewer.md) |
| Commands: design doc first, new endpoint checklist | [`.claude/commands/`](.claude/commands/) |
| Layer rules as a test | [`tests/test_architecture.py`](tests/test_architecture.py) |
| Design docs, approved before code | [`docs/design/`](docs/design/) |
| Architecture decisions and their reasons | [`docs/adr/`](docs/adr/) |
| Pull request history with reviews and fixes | [Pull requests](https://github.com/JasperBTA/budget-api/pulls?q=is%3Apr) |
