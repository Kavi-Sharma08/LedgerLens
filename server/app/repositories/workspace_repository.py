from bson import ObjectId

from ..core.errors import NotFoundError
from ..models.workspace import Workspace

COLLECTION = "workspaces"


async def slug_exists(db, slug: str) -> bool:
    return await db[COLLECTION].find_one({"slug": slug}) is not None


async def create_workspace(db, workspace: Workspace) -> Workspace:
    result = await db[COLLECTION].insert_one(workspace.to_document())
    workspace.id = result.inserted_id
    return workspace


async def get_by_id(db, workspace_id: str | ObjectId) -> Workspace:
    """Fetch a workspace by its id. Raises NotFoundError if absent."""
    doc = await db[COLLECTION].find_one({"_id": ObjectId(workspace_id)})
    if doc is None:
        raise NotFoundError(message="Workspace not found.")
    return Workspace.from_document(doc)


async def list_for_owner(db, owner_id: str | ObjectId) -> list[Workspace]:
    cursor = (
        db[COLLECTION]
        .find({"ownerId": ObjectId(owner_id)})
        .sort("createdAt", 1)
    )
    return [Workspace.from_document(doc) async for doc in cursor]


async def first_for_owner(db, owner_id: str | ObjectId) -> Workspace | None:
    """Day 1 users own exactly one workspace; returns it if present."""
    doc = await db[COLLECTION].find_one({"ownerId": ObjectId(owner_id)})
    return Workspace.from_document(doc) if doc else None


async def update_workspace(db, workspace_id: str | ObjectId, updates: dict) -> Workspace:
    """Update workspace fields and return the refreshed document."""
    from datetime import datetime, timezone

    updates["updatedAt"] = datetime.now(timezone.utc)
    doc = await db[COLLECTION].find_one_and_update(
        {"_id": ObjectId(workspace_id)},
        {"$set": updates},
        return_document=True,
    )
    if doc is None:
        raise NotFoundError(message="Workspace not found.")
    return Workspace.from_document(doc)
