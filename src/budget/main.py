from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from budget.api import auth, budgets, categories, reports, transactions
from budget.errors import BusinessRuleError, ConflictError, DomainError, NotFoundError

STATUS_BY_ERROR: dict[type[DomainError], int] = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ConflictError: status.HTTP_409_CONFLICT,
    BusinessRuleError: status.HTTP_422_UNPROCESSABLE_CONTENT,
}

app = FastAPI(title="Budget API", version="0.1.0")

for module in (auth, categories, transactions, budgets, reports):
    app.include_router(module.router)


@app.exception_handler(DomainError)
async def domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
    code = STATUS_BY_ERROR.get(type(exc), status.HTTP_400_BAD_REQUEST)
    return JSONResponse({"detail": str(exc)}, status_code=code)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}
