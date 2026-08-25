"""Domain-level errors mapped to HTTP responses in main.py.

Services and repositories raise these; routes stay thin.
"""


class AppError(Exception):
    status_code = 500
    code = "internal_error"
    message = "Something went wrong on our side. Please try again."

    def __init__(
        self,
        message: str | None = None,
        *,
        status_code: int | None = None,
        code: str | None = None,
    ):
        if message:
            self.message = message
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code
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


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"
    message = "You don't have permission to do this."


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    message = "We couldn't find what you were looking for."


# --- Financial domain errors (Phase 2) -------------------------------------


class SourceNotFoundError(NotFoundError):
    code = "source_not_found"
    message = "That financial source doesn't exist."


class SourceFileNotFoundError(NotFoundError):
    code = "file_not_found"
    message = "That file doesn't exist."


class TransactionNotFoundError(NotFoundError):
    code = "transaction_not_found"
    message = "That transaction doesn't exist."


class ReconciliationRunNotFoundError(NotFoundError):
    code = "run_not_found"
    message = "That reconciliation run doesn't exist."


class InvalidSourceError(AppError):
    status_code = 400
    code = "invalid_source"
    message = "The financial source details aren't valid."


class DuplicateSourceError(AppError):
    status_code = 409
    code = "duplicate_source"
    message = "A source with this name already exists in your workspace."


class InvalidFileError(AppError):
    status_code = 400
    code = "invalid_file"
    message = "This file couldn't be read as a financial import. Check the format and try again."


class DuplicateFileError(AppError):
    status_code = 409
    code = "duplicate_file"
    message = "An identical file was already imported for this source."


class UnsupportedCurrencyError(AppError):
    status_code = 422
    code = "unsupported_currency"
    message = "That currency isn't supported yet."


class InvalidDateError(AppError):
    status_code = 422
    code = "invalid_date"
    message = "One of the dates provided isn't valid."


class ReconciliationFailedError(AppError):
    status_code = 500
    code = "reconciliation_failed"
    message = "The reconciliation couldn't be completed. Please try again."
