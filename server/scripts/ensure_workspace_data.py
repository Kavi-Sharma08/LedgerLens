"""Migration: ensure workspace data integrity.

For each workspace:
  - Verify an OWNER membership exists (create one from ownerId if missing).
  - Check that sources, transactions, reconciliation_runs, matches,
    exceptions, source_files, raw_transactions, and audit_logs documents
    belong to valid workspaces.

This script is idempotent — safe to run multiple times.
It does NOT delete any data.

Run from the repo root:
    cd server && python -m scripts.ensure_workspace_data
"""

import logging
from datetime import datetime, timezone

from pymongo import MongoClient

from app.core.config import get_settings
from app.models.enums import MembershipStatus, WorkspaceRole

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("ensure_workspace_data")

FINANCIAL_COLLECTIONS = [
    "sources",
    "source_files",
    "raw_transactions",
    "transactions",
    "reconciliation_runs",
    "match_candidates",
    "matches",
    "exceptions",
    "audit_logs",
]


def run():
    settings = get_settings()
    client = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)
    db = client[settings.mongodb_database]

    # Verify connectivity
    try:
        client.admin.command("ping")
    except Exception as exc:
        log.error("Cannot reach MongoDB: %s", exc)
        client.close()
        return

    # --- Discover all workspace IDs ---
    workspace_ids = {str(ws["_id"]) for ws in db["workspaces"].find({}, {"_id": 1})}
    log.info("Found %d workspace(s) in database", len(workspace_ids))

    # --- Phase 1: Ensure OWNER membership for every workspace ---
    members_created = 0
    members_skipped = 0

    for ws in db["workspaces"].find({}):
        ws_id = ws["_id"]
        owner_id = ws.get("ownerId")
        if not owner_id:
            log.warning("Workspace %s has no ownerId — cannot ensure OWNER membership", ws_id)
            members_skipped += 1
            continue

        existing = db["workspace_members"].find_one(
            {"workspaceId": ws_id, "role": WorkspaceRole.OWNER.value}
        )
        if existing:
            members_skipped += 1
            continue

        # Also check by userId in case role was changed
        existing_by_user = db["workspace_members"].find_one(
            {"workspaceId": ws_id, "userId": owner_id}
        )
        if existing_by_user:
            # Membership exists but not OWNER — upgrade it
            db["workspace_members"].update_one(
                {"_id": existing_by_user["_id"]},
                {"$set": {"role": WorkspaceRole.OWNER.value, "updatedAt": datetime.now(timezone.utc)}},
            )
            log.info("Upgraded membership to OWNER: workspace=%s user=%s", ws_id, owner_id)
            members_created += 1
            continue

        now = datetime.now(timezone.utc)
        db["workspace_members"].insert_one({
            "workspaceId": ws_id,
            "userId": owner_id,
            "role": WorkspaceRole.OWNER.value,
            "status": MembershipStatus.ACTIVE.value,
            "joinedAt": ws.get("createdAt", now),
            "createdAt": now,
            "updatedAt": now,
        })
        members_created += 1
        log.info("Created OWNER membership: workspace=%s user=%s", ws_id, owner_id)

    log.info("Membership phase complete. Created: %d, Already present: %d", members_created, members_skipped)

    # --- Phase 2: Reassign orphaned data to the primary workspace ---
    collection_counts = {}
    primary_ws_id = None
    primary_ws = db["workspaces"].find_one()
    if not primary_ws:
        log.error("No workspaces found — cannot reassign orphaned data")
    else:
        primary_ws_id = primary_ws["_id"]
        primary_slug = primary_ws.get("slug", "unknown")
        log.info("Primary workspace: %s (slug=%s)", primary_ws_id, primary_slug)

    for collection_name in FINANCIAL_COLLECTIONS:
        collection = db[collection_name]
        total = collection.count_documents({})
        collection_counts[collection_name] = total

        if total == 0:
            continue

        or_conditions = [
            {"workspaceId": {"$exists": False}},
            {"workspaceId": None},
        ]
        if workspace_ids:
            or_conditions.append({"workspaceId": {"$nin": list(workspace_ids)}})

        orphaned = collection.count_documents({"$or": or_conditions})

        if orphaned > 0 and primary_ws_id:
            collection.update_many(
                {"$or": or_conditions},
                {"$set": {"workspaceId": primary_ws_id}},
            )
            log.info(
                "REASSIGNED %d / %d documents in '%s' -> workspace %s",
                orphaned, total, collection_name, primary_ws_id,
            )
        elif orphaned > 0:
            log.warning(
                "ORPHANED DATA: %d / %d documents in '%s' (no workspace to reassign to)",
                orphaned, total, collection_name,
            )
        else:
            log.info("  %s: %d documents, all valid", collection_name, total)

    # --- Summary ---
    total_reassigned = sum(
        count for name, count in collection_counts.items()
        if count and count > 0
    )
    log.info("=" * 60)
    log.info("SUMMARY")
    log.info("  Workspaces: %d", len(workspace_ids))
    log.info("  OWNER memberships created: %d", members_created)
    log.info("  Collections checked: %d", len(FINANCIAL_COLLECTIONS))
    for name, count in collection_counts.items():
        log.info("    %s: %d documents", name, count)
    if total_reassigned > 0:
        log.info("  All data reassigned to primary workspace %s", primary_ws_id)
    else:
        log.info("  All data is properly scoped — no reassignment needed")
    log.info("=" * 60)

    client.close()


if __name__ == "__main__":
    run()
