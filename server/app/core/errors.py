"""Domain-level errors mapped to HTTP responses in main.py.

Services and repositories raise these; routes stay thin.
"""


class AppError(Exception):
    status_code = 500
    code = "internal_error"
    message = "Something went wrong on our side. Please try again."

    def __init__(self, message: str | None = None):
        if message:
            self.message = message
        super().__init__(self.message)


class DatabaseUnavailableError(AppError):
    status_code = 503
    code = "database_unavailable"
    message = (
        "LedgerLens is temporarily unable to reach its database. "
        "Please try again in a few moments."
    )


class EmailAlreadyRegisteredError(AppError):
    status_code = 409
    code = "email_already_registered"
    message = "An account with this email already exists."


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"
    message = "Your session has expired or is invalid. Please sign in again."


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    message = "We couldn't find what you were looking for."
