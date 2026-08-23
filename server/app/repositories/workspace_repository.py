from bson import ObjectId

from ..models.workspace import Workspace

COLLECTION = "workspaces"


async def slug_exists(db, slug: str) -> bool:
    return await db[COLLECTION].find_one({"slug": slug}) is not None


async def create_workspace(db, workspace: Workspace) -> Workspace:
    result = await db[COLLECTION].insert_one(workspace.to_document())
    workspace.id = result.inserted_id
    return workspace


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
