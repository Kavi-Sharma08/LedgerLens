from fastapi import APIRouter, Depends, Query

from ...api.deps import get_current_workspace
from ...core.database import get_database
from ...core.errors import AppError
from ...models.enums import Direction, TransactionStatus, TransactionType
from ...models.workspace import Workspace
from ...repositories import transaction_repository
from ...repositories.common import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, InvalidCursorError
from ...repositories.transaction_repository import TransactionFilter
from ...schemas.common import paginated
from ...services.mappers import to_match_public, to_transaction_public
from ...services.normalization.dates import DateError, parse_date_value

router = APIRouter()


@router.get("")
async def list_transactions(
    sourceId: str | None = Query(default=None),
    dateFrom: str | None = Query(default=None),
    dateTo: str | None = Query(default=None),
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    direction: Direction | None = Query(default=None),
    status: TransactionStatus | None = Query(default=None),
    type: TransactionType | None = Query(default=None),
    search: str | None = Query(default=None, max_length=120),
    limit: int | None = Query(default=None, ge=1, le=MAX_PAGE_SIZE),
    cursor: str | None = Query(default=None),
    workspace: Workspace = Depends(get_current_workspace),
    db=Depends(get_database),
):
    """Cursor-paginated canonical transactions with optional filters.

    New filters belong in `TransactionFilter`, never in this signature's
    ad-hoc query logic."""
    try:
        query_filter = TransactionFilter(
            source_id=_parse_object_id(sourceId),
            date_from=parse_date_value(dateFrom) if dateFrom else None,
            date_to=parse_date_value(dateTo) if dateTo else None,
            currency=currency,
            direction=direction.value if direction else None,
            status=status.value if status else None,
            transaction_type=type.value if type else None,
            search=search,
        )
    except DateError as exc:
        raise AppError(status_code=422, message=str(exc))

    try:
        page = await transaction_repository.list_transactions(
            db, workspace.id, query_filter, limit=limit, cursor=cursor
        )
    except InvalidCursorError:
        raise AppError(status_code=400, message="Pagination cursor is invalid.")
    return paginated(
        [to_transaction_public(t) for t in page.items],
        limit or DEFAULT_PAGE_SIZE,
        page.next_cursor,
    )


@router.get("/{transaction_id}")
async def get_transaction(
    transaction_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    db=Depends(get_database),
):
    from ...core.errors import TransactionNotFoundError
    from bson import ObjectId

    try:
        _id = ObjectId(transaction_id)
    except Exception:
        raise TransactionNotFoundError()
    txn = await transaction_repository.get_by_id(db, workspace.id, _id)
    if txn is None:
        raise TransactionNotFoundError()
    return to_transaction_public(txn)


@router.get("/{transaction_id}/matches")
async def list_transaction_matches(
    transaction_id: str,
    limit: int | None = Query(default=None, ge=1, le=MAX_PAGE_SIZE),
    cursor: str | None = Query(default=None),
    workspace: Workspace = Depends(get_current_workspace),
    db=Depends(get_database),
):
    """Reconciliation evidence for one transaction: the match groups it
    belongs to, newest first. Powers the transaction detail drawer."""
    from ...core.errors import TransactionNotFoundError
    from ...repositories import match_repository
    from bson import ObjectId

    try:
        _id = ObjectId(transaction_id)
    except Exception:
        raise TransactionNotFoundError()

    txn = await transaction_repository.get_by_id(db, workspace.id, _id)
    if txn is None:
        raise TransactionNotFoundError()

    try:
        page = await match_repository.list_for_transaction(
            db, workspace.id, _id, limit=limit, cursor=cursor
        )
    except InvalidCursorError:
        raise AppError(status_code=400, message="Pagination cursor is invalid.")
    return paginated(
        [to_match_public(m) for m in page.items],
        limit or DEFAULT_PAGE_SIZE,
        page.next_cursor,
    )


def _parse_object_id(value: str | None):
    from bson import ObjectId

    if not value:
        return None
    try:
        return ObjectId(value)
    except Exception as exc:
        from ...core.errors import InvalidSourceError

        raise InvalidSourceError("That source id isn't valid.") from exc
