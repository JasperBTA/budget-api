"""Domain errors. Services raise these; the API layer maps them to HTTP status codes."""


class DomainError(Exception):
    pass


class NotFoundError(DomainError):
    pass


class ConflictError(DomainError):
    pass


class BusinessRuleError(DomainError):
    pass
