"""Migration: create OWNER WorkspaceMember records for all existing workspaces.

Every workspace that exists before the membership system must have an OWNER
record so its creator retains full access.

Run from the repo root:
    cd server && python -m scripts.migrate_add_memberships

Safe to run multiple times (idempotent — skips workspaces that already
have a member).
"""

import asyncio
import logging
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import get_settings
from app.models.enums import MembershipStatus, WorkspaceRole

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("migrate_memberships")

COLLECTION_WORKSPACES = "workspaces"
COLLECTION_MEMBERS = "workspace_members"


async def migrate():
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_database]

    cursor = db[COLLECTION_WORKSPACES].find({})
    migrated = 0
    skipped = 0

    async for ws in cursor:
        workspace_id = ws["_id"]
        owner_id = ws.get("ownerId")
        if not owner_id:
            log.warning("Workspace %s has no ownerId — skipping", workspace_id)
            skipped += 1
            continue

        # Check if a member already exists for this workspace
        existing = await db[COLLECTION_MEMBERS].find_one(
            {"workspaceId": workspace_id, "userId": owner_id}
        )
        if existing:
            skipped += 1
            continue

        now = datetime.now(timezone.utc)
        await db[COLLECTION_MEMBERS].insert_one({
            "workspaceId": workspace_id,
            "userId": owner_id,
            "role": WorkspaceRole.OWNER.value,
            "status": MembershipStatus.ACTIVE.value,
            "joinedAt": ws.get("createdAt", now),
            "createdAt": now,
            "updatedAt": now,
        })
        migrated += 1
        log.info("Created OWNER membership: workspace=%s user=%s", workspace_id, owner_id)

    log.info("Migration complete. Migrated: %d, Skipped: %d", migrated, skipped)
    client.close()


if __name__ == "__main__":
    asyncio.run(migrate())
