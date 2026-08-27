"""Overview summary for the dashboard.

One call returning the honest headline numbers a finance user needs first:
how much data exists, how many sources feed it, what is still open, and the
outcome of the most recent reconciliation (if any)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...api.deps import get_current_workspace, require_permission
from ...core.database import get_database
from ...models.workspace import Workspace
from ...repositories import (
    exception_repository,
    source_repository,
    transaction_repository,
    reconciliation_run_repository,
)
from ...schemas.reconciliation import RunPublic
from ...services.mappers import to_run_public

router = APIRouter()


class OverviewPublic(BaseModel):
    totalTransactions: int
    sourcesCount: int
    openExceptions: int
    latestRun: RunPublic | None = None


@router.get("", response_model=OverviewPublic)
async def get_overview(
    workspace: Workspace = Depends(get_current_workspace),
    db=Depends(get_database),
    __=Depends(require_permission("view_data")),
):
    total_transactions = await transaction_repository.count_transactions(
        db, workspace.id, transaction_repository.TransactionFilter()
    )
    sources_count = await source_repository.count_sources(db, workspace.id)
    open_exceptions = await exception_repository.count_open(db, workspace.id)

    runs_page = await reconciliation_run_repository.list_runs(db, workspace.id, limit=1)
    latest_run = to_run_public(runs_page.items[0]) if runs_page.items else None

    return OverviewPublic(
        totalTransactions=total_transactions,
        sourcesCount=sources_count,
        openExceptions=open_exceptions,
        latestRun=latest_run,
    )
