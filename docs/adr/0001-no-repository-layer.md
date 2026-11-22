# ADR 0001 — No repository layer

Status: accepted · 2026-11-22

## Context

Layered FastAPI projects often add a repository class per table between services and SQLAlchemy.
Here services already receive a `Session`, which is SQLAlchemy's unit of work and identity map,
and queries are a few lines each.

## Decision

Services use the `Session` directly. No repository classes, no generic CRUD base.

## Consequences

- One less layer to read: a service function shows the query it runs.
- Tests run services against real PostgreSQL in a rolled-back transaction instead of mocking a
  repository, so constraints and `Numeric` behave as in production.
- The architecture test still keeps SQL out of `api/` (`tests/test_architecture.py`).
- Revisit only when a second storage implementation appears; that is the point where an
  interface earns its cost.
