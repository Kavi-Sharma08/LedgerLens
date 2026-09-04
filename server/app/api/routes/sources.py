from fastapi import APIRouter, Depends, Query

from ...api.deps import get_current_user, get_current_workspace, require_permission
from ...core.database import get_database
from ...core.errors import AppError
from ...models.enums import SourceType
from ...models.user import User
from ...models.workspace import Workspace
from ...repositories import source_repository
from ...repositories.common import InvalidCursorError, MAX_PAGE_SIZE, DEFAULT_PAGE_SIZE
from ...schemas.common import paginated
from ...schemas.source import SourceCreate, SourcePublic, SourceUpdate
from ...services.mappers import to_source_public
from ...services.source_service import create_source, update_source, delete_source

router = APIRouter()


@router.post("", response_model=SourcePublic, status_code=201)
async def create_financial_source(
    payload: SourceCreate,
    workspace: Workspace = Depends(get_current_workspace),
    db=Depends(get_database),
    _: User = Depends(get_current_user),
    __=Depends(require_permission("manage_sources")),
):
    """Register a logical financial source (bank, gateway, ledger...)."""
    source = await create_source(
        db,
        workspace.id,
        name=payload.name,
        source_type=payload.type,
        institution=payload.institution,
        account_identifier=payload.accountIdentifier,
        currency=payload.currency,
    )
    return to_source_public(source)


@router.get("")
async def list_financial_sources(
    type: SourceType | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=MAX_PAGE_SIZE),
    cursor: str | None = Query(default=None),
    workspace: Workspace = Depends(get_current_workspace),
    db=Depends(get_database),
    __=Depends(require_permission("view_data")),
):
    try:
        page = await source_repository.list_sources(
            db,
            workspace.id,
            source_type=type,
            limit=limit,
            cursor=cursor,
        )
    except InvalidCursorError:
        raise AppError(status_code=400, message="Pagination cursor is invalid.")
    return paginated(
        [to_source_public(s) for s in page.items],
        limit or DEFAULT_PAGE_SIZE,
        page.next_cursor,
    )


@router.get("/{source_id}", response_model=SourcePublic)
async def get_financial_source(
    source_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    db=Depends(get_database),
    __=Depends(require_permission("view_data")),
):
    source = await source_repository.get_by_id(db, workspace.id, source_id)
    return to_source_public(source)


@router.patch("/{source_id}", response_model=SourcePublic)
async def update_financial_source(
    source_id: str,
    payload: SourceUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    db=Depends(get_database),
    _: User = Depends(get_current_user),
    __=Depends(require_permission("manage_sources")),
):
    """Update a source's name, institution, or currency."""
    source = await update_source(
        db,
        workspace.id,
        source_id,
        name=payload.name,
        institution=payload.institution,
        currency=payload.currency,
    )
    return to_source_public(source)


@router.delete("/{source_id}", status_code=204)
async def delete_financial_source(
    source_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    db=Depends(get_database),
    _: User = Depends(get_current_user),
    __=Depends(require_permission("manage_sources")),
):
    """Delete a source and all its imported data."""
    await delete_source(db, workspace.id, source_id)
