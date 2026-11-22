FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH"
WORKDIR /app

# Dependencies first, so code changes don't invalidate this layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

RUN useradd --create-home app
USER app

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn budget.main:app --host 0.0.0.0 --port 8000"]
