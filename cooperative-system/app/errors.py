"""Domain errors, mapped to HTTP status codes in ``app.main``."""


class DomainError(Exception):
    status_code = 400

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class NotFound(DomainError):
    status_code = 404


class Conflict(DomainError):
    status_code = 409


class BusinessRuleViolation(DomainError):
    status_code = 422
