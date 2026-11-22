---
description: Add an API endpoint the way AGENTS.md requires, layer by layer, with its tests.
argument-hint: <METHOD /path and what it does>
---

Add this endpoint: $ARGUMENTS

Follow `AGENTS.md`. Work through the list in order and do not skip an item; say so explicitly if
one does not apply.

1. **Design**: if it adds a table, a business rule or a new resource, run `/design-doc` first.
2. **Model and migration** (only if the schema changes): edit `models.py`, then
   `uv run alembic revision --autogenerate --rev-id 0003 -m "<what>"` (next free 4-digit number),
   read and fix the file;
   add `CHECK` constraints by hand. Never edit a migration already on `main`.
3. **Domain**: pure calculations and value rules go to `domain/`, with unit tests in `tests/unit/`.
4. **Service**: a function in `services/` taking plain values (`user_id: int`, `Decimal`, `date`);
   scope every query through `Category.user_id`; raise `NotFoundError` / `ConflictError` /
   `BusinessRuleError`; rely on constraints and catch `IntegrityError` instead of check-then-write.
   No imports of FastAPI, `schemas` or `HTTPException` here.
5. **Schemas**: request/response models in `schemas.py`; `Money`, `Month` and `Id` types for
   amounts, months and ids. Lists that can grow without bound take `limit` (1–100, default 50)
   and `offset` with a deterministic order.
6. **Router**: thin, in `api/`: validate, call one service function, return a response schema;
   never an ORM object or a dict; `201` create, `204` delete, `200` otherwise. A new router module
   is imported in `main.py` and added to the router tuple there.
7. **Tests** in `tests/api/`: the happy path with exact values, every rule's failure (4xx, never
   500), and a user-isolation test with `alice` and `bob` (another user's resource is 404). A rule
   enforced by a database constraint also gets a test that bypasses the app and hits the DB.
8. **Checks**: the full command from `AGENTS.md`, then a review with the `reviewer` subagent.
