# ADR 0003 — Money is `Decimal`, end to end

Status: accepted · recorded 2026-11-22 (decision taken in the initial commits)

## Context

Binary floats cannot represent most cents exactly (`0.1 + 0.2 != 0.3`), and totals drift when
many amounts are summed. JSON numbers are usually parsed as floats by clients.

## Decision

- Database: `Numeric(12, 2)`.
- Python: `Decimal`, never `float`; zero is `Decimal("0.00")`.
- API: amounts are strings with exactly two decimals (`"12.50"`); input is validated and
  quantized by the `Money` type in `schemas.py`, so `"12.5"` comes back as `"12.50"`.

## Consequences

- Report totals are exact; tests compare strings (`"630.10"`), which also checks the scale.
- Responses carry amounts as strings. Clients should send strings too: JSON numbers are
  accepted and quantized, but a client that builds them from floats may already have lost
  precision.
- Amounts are always positive; income vs expense comes from the category (AGENTS.md, rule 2).
