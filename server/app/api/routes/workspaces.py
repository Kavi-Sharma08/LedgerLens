from fastapi import APIRouter, Depends

from ...api.deps import get_current_user
from ...core.database import get_database
from ...core.errors import NotFoundError
from ...models.user import User
from ...repositories import workspace_repository
from ...schemas.user import WorkspacePublic
from ...services.mappers import to_workspace_public

router = APIRouter()


@router.get("/current", response_model=WorkspacePublic)
async def read_current_workspace(
    current_user: User = Depends(get_current_user),
    db=Depends(get_database),
):
    """The signed-in user's active workspace.

    Day 1: users own exactly one workspace, created at signup. Multi-workspace
    membership and roles arrive with WorkspaceMember in later days.
    """
    workspace = await workspace_repository.first_for_owner(db, str(current_user.id))
    if workspace is None:
        raise NotFoundError(message="You don't have an active workspace yet.")
    return to_workspace_public(workspace)
