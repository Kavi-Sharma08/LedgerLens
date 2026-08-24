from fastapi import APIRouter, Depends, Query, Request

from ...api.deps import get_current_workspace
from ...core.database import get_database
from ...core.errors import AppError
from ...models.workspace import Workspace
from ...repositories.common import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, InvalidCursorError
from ...repositories import source_file_repository
from ...schemas.common import paginated
from ...schemas.file import FilePublic, FileUploadResponse
from ...services.mappers import to_file_public
from ...services.source_service import upload_source_file

router = APIRouter()


@router.post("/upload", response_model=FileUploadResponse, status_code=201)
async def upload_source_file_route(
    request: Request,
    sourceId: str = Query(...),
    fileName: str = Query(...),
    mimeType: str | None = Query(default=None),
    workspace: Workspace = Depends(get_current_workspace),
    db=Depends(get_database),
):
    """Import a financial file (CSV/JSONL) for a source.

    The raw bytes are the request body — no multipart dependency required.
    Re-uploading identical content is idempotent: the response reports the
    original import with `isDuplicate: true` and nothing is re-ingested."""
    content = await request.body()
    source = await _get_source(db, workspace, sourceId)

    summary = await upload_source_file(
        db,
        workspace.id,
        source=source,
        file_name=fileName,
        mime_type=mimeType,
        content=content,
        uploaded_by=None,  # actor resolution rides with the session; stored later
    )
    return FileUploadResponse(
        file=to_file_public(summary.file),
        isDuplicate=summary.is_duplicate,
    )


async def _get_source(db, workspace, source_id):
    from ...repositories import source_repository

    return await source_repository.get_by_id(db, workspace.id, source_id)


@router.get("")
async def list_files_for_source(
    sourceId: str = Query(...),
    limit: int | None = Query(default=None, ge=1, le=MAX_PAGE_SIZE),
    cursor: str | None = Query(default=None),
    workspace: Workspace = Depends(get_current_workspace),
    db=Depends(get_database),
):
    source = await _get_source(db, workspace, sourceId)
    try:
        page = await source_file_repository.list_for_source(
            db, workspace.id, source.id, limit=limit, cursor=cursor
        )
    except InvalidCursorError:
        raise AppError(status_code=400, message="Pagination cursor is invalid.")
    return paginated(
        [to_file_public(f) for f in page.items],
        limit or DEFAULT_PAGE_SIZE,
        page.next_cursor,
    )


@router.get("/{file_id}", response_model=FilePublic)
async def get_source_file(
    file_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    db=Depends(get_database),
):
    source_file = await source_file_repository.get_by_id(db, workspace.id, file_id)
    return to_file_public(source_file)
