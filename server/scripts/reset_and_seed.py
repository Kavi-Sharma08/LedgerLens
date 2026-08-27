"""Reset and seed the development database with deterministic synthetic data.

This script:
1. Removes stale synthetic LedgerLens data
2. Creates a deterministic development user with a bcrypt-hashed password
3. Creates a deterministic workspace owned by that user
4. Creates an OWNER membership
5. Seeds all financial data through the real ingestion pipeline
6. Verifies every record references the correct workspace
7. Prints a concise summary

Usage:
    cd server
    python -m scripts.reset_and_seed
    python -m scripts.reset_and_seed --dump-ground-truth
"""

import argparse
import asyncio
import csv
import io
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bson import ObjectId  # noqa: E402

from app.core.database import (  # noqa: E402
    _ensure_indexes,
    close_mongo,
    connect_to_mongo,
    mongo,
)
from app.models.enums import SourceType  # noqa: E402
from app.models.source import Source  # noqa: E402
from app.models.workspace import Workspace  # noqa: E402
from app.models.workspace_member import WorkspaceMember  # noqa: E402
from app.models.enums import MembershipStatus, WorkspaceRole  # noqa: E402
from app.repositories.source_repository import create_source, list_sources  # noqa: E402
from app.repositories.workspace_repository import create_workspace, slug_exists  # noqa: E402
from app.repositories.workspace_member_repository import create_member  # noqa: E402
from app.services.source_service import upload_source_file  # noqa: E402
from app.synthetic.dataset import (  # noqa: E402
    ACCOUNTING,
    BANK,
    GATEWAY,
    SOURCE_NAMES,
    records_for_source,
)

# ---------------------------------------------------------------------------
# Deterministic dev credentials
# ---------------------------------------------------------------------------
DEV_EMAIL = "kavi@ledgerlens.dev"
DEV_PASSWORD = "Kavi@123"
DEV_NAME = "Kavi Sharma"
WORKSPACE_NAME = "LedgerLens Demo"

# Bcrypt rounds matching the Next.js registration module
BCRYPT_ROUNDS = 12


def hash_password(password: str) -> str:
    """Hash a password using bcrypt, matching the Next.js bcryptjs usage."""
    import bcrypt
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("utf-8")


def build_csv(records) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(
        ["Date", "Amount", "Description", "Reference", "Counterparty", "Currency", "Type", "Status", "TxnId"]
    )
    for r in records:
        writer.writerow(
            [r.date, r.amount, r.description, r.reference, r.counterparty,
             r.currency, r.type, r.status, r.rid]
        )
    return buffer.getvalue().encode("utf-8")


async def reset_stale_data(db) -> dict:
    """Remove stale synthetic development data from financial collections."""
    collections_to_clear = [
        "sources",
        "source_files",
        "raw_transactions",
        "transactions",
        "reconciliation_runs",
        "match_candidates",
        "matches",
        "exceptions",
        "audit_logs",
        "invitations",
    ]
    counts = {}
    for coll_name in collections_to_clear:
        result = await db[coll_name].delete_many({})
        counts[coll_name] = result.deleted_count
    return counts


async def ensure_dev_user(db) -> ObjectId:
    """Create or update the deterministic dev user. Returns the user's ObjectId."""
    existing = await db["users"].find_one({"email": DEV_EMAIL})

    password_hash = hash_password(DEV_PASSWORD)

    if existing:
        # Update password hash in case it changed
        await db["users"].update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "passwordHash": password_hash,
                "name": DEV_NAME,
                "updatedAt": datetime.now(timezone.utc),
            }}
        )
        return existing["_id"]

    now = datetime.now(timezone.utc)
    user_id = ObjectId()
    await db["users"].insert_one({
        "_id": user_id,
        "name": DEV_NAME,
        "email": DEV_EMAIL,
        "emailVerified": None,
        "image": None,
        "avatar": None,
        "passwordHash": password_hash,
        "createdAt": now,
        "updatedAt": now,
    })
    return user_id


async def ensure_workspace(db, user_id: ObjectId) -> ObjectId:
    """Create or find the deterministic workspace. Returns workspace ObjectId."""
    # Check for existing workspace by name
    existing = await db["workspaces"].find_one({"name": WORKSPACE_NAME})
    if existing:
        return existing["_id"]

    now = datetime.now(timezone.utc)
    slug = "ledgerlens-demo"
    if await slug_exists(db, slug):
        slug = f"ledgerlens-demo-{int(now.timestamp())}"

    workspace = Workspace(
        name=WORKSPACE_NAME,
        slug=slug,
        owner_id=user_id,
        created_at=now,
        updated_at=now,
    )
    workspace = await create_workspace(db, workspace)
    return workspace.id


async def ensure_owner_membership(db, user_id: ObjectId, workspace_id: ObjectId) -> None:
    """Create OWNER membership if it doesn't exist."""
    existing = await db["workspace_members"].find_one({
        "workspaceId": workspace_id,
        "userId": user_id,
    })
    if existing:
        return

    now = datetime.now(timezone.utc)
    member = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=user_id,
        role=WorkspaceRole.OWNER,
        status=MembershipStatus.ACTIVE,
        joined_at=now,
        created_at=now,
        updated_at=now,
    )
    await create_member(db, member)


async def seed_financial_data(db, workspace_id: ObjectId) -> dict:
    """Seed all financial data through the real ingestion pipeline."""
    source_ids = {}
    for key in (BANK, GATEWAY, ACCOUNTING):
        name, type_name = SOURCE_NAMES[key]
        existing = await db["sources"].find_one({
            "workspaceId": workspace_id,
            "name": name,
        })
        if existing:
            source_ids[key] = existing["_id"]
            continue
        source = await create_source(
            db,
            workspace_id,
            Source(workspace_id=workspace_id, name=name, type=SourceType(type_name), currency="INR"),
        )
        source_ids[key] = source.id

    totals = {}
    for key in (BANK, GATEWAY, ACCOUNTING):
        records = records_for_source(key)
        content = build_csv(records)
        source_doc = await db["sources"].find_one({"_id": source_ids[key]})
        source = Source.from_document(source_doc)
        summary = await upload_source_file(
            db, workspace_id,
            source=source,
            file_name=f"synthetic_{key.lower()}_aug_2026.csv",
            mime_type="text/csv",
            content=content,
            uploaded_by=None,
        )
        totals[key] = {
            "processed": summary.processed_count,
            "skipped_duplicates": summary.skipped_duplicate_count,
            "errors": summary.error_count,
        }

    return totals


async def verify_workspace_scoped(db, workspace_id: ObjectId) -> dict:
    """Verify every workspace-scoped record references the correct workspace."""
    collections_to_check = [
        "sources",
        "source_files",
        "raw_transactions",
        "transactions",
        "reconciliation_runs",
        "matches",
        "match_candidates",
        "exceptions",
        "audit_logs",
    ]
    verification = {}
    for coll_name in collections_to_check:
        total = await db[coll_name].count_documents({})
        correct = await db[coll_name].count_documents({"workspaceId": workspace_id})
        orphaned = total - correct
        verification[coll_name] = {"total": total, "correct": correct, "orphaned": orphaned}
        if orphaned > 0:
            print(f"  WARNING: {coll_name} has {orphaned} orphaned records!")
    return verification


async def seed(dump_ground_truth: bool = False) -> dict:
    """Main seed entry point."""
    connected = await connect_to_mongo()
    if not connected:
        print("MongoDB is not reachable. Start it and retry.")
        sys.exit(1)

    db = mongo.db
    await _ensure_indexes(db)

    print("Resetting stale synthetic data...")
    reset_counts = await reset_stale_data(db)
    removed_total = sum(reset_counts.values())
    print(f"  Removed {removed_total} stale records")

    print("\nCreating development user...")
    user_id = await ensure_dev_user(db)
    print(f"  User: {DEV_EMAIL} (id={user_id})")

    print("\nCreating workspace...")
    workspace_id = await ensure_workspace(db, user_id)
    print(f"  Workspace: {WORKSPACE_NAME} (id={workspace_id})")

    print("\nEnsuring OWNER membership...")
    await ensure_owner_membership(db, user_id, workspace_id)
    print("  Membership: OWNER (ACTIVE)")

    print("\nSeeding financial data...")
    totals = await seed_financial_data(db, workspace_id)

    print("\nVerifying workspace-scoped data...")
    verification = await verify_workspace_scoped(db, workspace_id)

    if dump_ground_truth:
        from app.synthetic.ground_truth import GROUND_TRUTH
        gt_path = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "synthetic_ground_truth.json"
        gt_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "description": "Expected reconciliation outcomes for the deterministic synthetic dataset.",
            "workspaceId": str(workspace_id),
            "entries": GROUND_TRUTH,
        }
        gt_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nGround truth written: {gt_path}")

    await close_mongo()

    # Count transaction totals
    txn_count = verification.get("transactions", {}).get("total", 0)
    match_count = verification.get("matches", {}).get("total", 0)
    exception_count = verification.get("exceptions", {}).get("total", 0)

    summary = {
        "user": DEV_EMAIL,
        "password": "(hashed, use Kavi@123 to log in)",
        "workspace": WORKSPACE_NAME,
        "workspaceId": str(workspace_id),
        "role": "OWNER",
        "sources": {k: v["processed"] for k, v in totals.items()},
        "totalTransactions": txn_count,
        "totalMatches": match_count,
        "totalExceptions": exception_count,
    }

    print("\n" + "=" * 60)
    print("Development seed completed")
    print("=" * 60)
    print(f"\n  User:       {DEV_EMAIL}")
    print(f"  Password:   Kavi@123")
    print(f"  Workspace:  {WORKSPACE_NAME}")
    print(f"  Role:       OWNER")
    print()
    print("  Sources:")
    for key, count in totals.items():
        print(f"    {key}: {count['processed']} transactions ingested")
    print()
    print(f"  Total transactions:   {txn_count}")
    print(f"  Total matches:        {match_count}")
    print(f"  Total exceptions:     {exception_count}")

    orphans = sum(v["orphaned"] for v in verification.values())
    if orphans == 0:
        print("\n  All records are workspace-scoped correctly.")
    else:
        print(f"\n  WARNING: {orphans} orphaned records detected!")

    print("=" * 60)

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset and seed LedgerLens dev database.")
    parser.add_argument("--dump-ground-truth", action="store_true")
    args = parser.parse_args()

    asyncio.run(seed(dump_ground_truth=args.dump_ground_truth))
