# ADR 0004 — Synchronous SQLAlchemy

Status: accepted · 2026-11-22

## Context

FastAPI supports async endpoints with an async database driver. This API does short CRUD queries
and one aggregate report per request; it has no long I/O waits or fan-out to other services.

## Decision

Use synchronous SQLAlchemy 2.x with `psycopg`, and plain `def` endpoints, which FastAPI runs in a
thread pool.

## Consequences

- Simpler code and tests: no `async`/`await` through services, no async test plugin, the same
  `Session` in the app, the tests and Alembic.
- Throughput is bounded by the thread pool and the connection pool, which is ample for this
  workload.
- Revisit if an endpoint has to wait on slow external calls, or if load tests show the thread
  pool as the bottleneck; the service layer takes plain values, so the change would stay
  inside `db.py`, `services/` and the routers.
