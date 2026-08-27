"""Read-only diagnostic: investigate transactions for a workspace.

Checks workspace existence, memberships, user data, and transaction
documents for workspace 6a8d742a3a5477b2a74477a6.

Run from the repo root:
    cd server && python -m scripts.diagnose_transactions
"""

import json
from datetime import datetime

from bson import ObjectId
from pymongo import MongoClient

from app.core.config import get_settings

TARGET_WORKSPACE = ObjectId("6a8d742a3a5477b2a74477a6")


def describe(value):
    """Return a human-friendly description of a value's type and repr."""
    if isinstance(value, ObjectId):
        return f"ObjectId('{value}')"
    if isinstance(value, datetime):
        return f"datetime({value.isoformat()})"
    return f"{type(value).__name__}({value!r})"


def run():
    settings = get_settings()
    client = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)
    db = client[settings.mongodb_database]

    print("=" * 70)
    print("LEDGERLENS TRANSACTION DIAGNOSTIC")
    print("=" * 70)
    print(f"Target workspace ID: 6a8d742a3a5477b2a74477a6")
    print(f"Database: {settings.mongodb_database}")
    print()

    # ── 1. Workspace ──────────────────────────────────────────────────────
    print("-" * 70)
    print("1. WORKSPACE")
    print("-" * 70)
    ws = db["workspaces"].find_one({"_id": TARGET_WORKSPACE})
    if ws:
        print(f"  EXISTS: yes")
        print(f"  _id type : {type(ws['_id']).__name__}")
        print(f"  _id value: {ws['_id']}")
        ws_str = {k: describe(v) for k, v in ws.items()}
        print(f"  Full document: {json.dumps(ws_str, indent=4, default=str)}")
    else:
        print("  EXISTS: NO — workspace not found in 'workspaces' collection")
        # Check if any document has a string version of the id
        ws_str = db["workspaces"].find_one({"_id": "6a8d742a3a5477b2a74477a6"})
        if ws_str:
            print("  NOTE: Found a document with _id as STRING — type mismatch!")
            print(f"  _id type : {type(ws_str['_id']).__name__}")
            print(f"  _id value: {ws_str['_id']}")
    print()

    # ── 2. Workspace members ──────────────────────────────────────────────
    print("-" * 70)
    print("2. WORKSPACE MEMBERSHIPS")
    print("-" * 70)
    members = list(db["workspace_members"].find({"workspaceId": TARGET_WORKSPACE}))
    # Also check with string key
    members_str = list(db["workspace_members"].find({"workspaceId": "6a8d742a3a5477b2a74477a6"}))
    print(f"  Members found (ObjectId match): {len(members)}")
    print(f"  Members found (string match)  : {len(members_str)}")
    all_members = {str(m["_id"]): m for m in members + members_str}
    for m in all_members.values():
        print(f"    userId={m.get('userId')}  role={m.get('role')}  status={m.get('status')}  workspaceId={describe(m.get('workspaceId'))}")
    # Show user IDs for next step
    user_ids = set()
    for m in all_members.values():
        uid = m.get("userId")
        if uid:
            user_ids.add(uid)
    print(f"  Distinct userId values: {user_ids}")
    print()

    # ── 3. Transactions ───────────────────────────────────────────────────
    print("-" * 70)
    print("3. TRANSACTIONS FOR TARGET WORKSPACE")
    print("-" * 70)
    tx_count_oid = db["transactions"].count_documents({"workspaceId": TARGET_WORKSPACE})
    tx_count_str = db["transactions"].count_documents({"workspaceId": "6a8d742a3a5477b2a74477a6"})
    print(f"  Count (ObjectId match): {tx_count_oid}")
    print(f"  Count (string match)  : {tx_count_str}")

    # Show first 2 documents from each match
    for label, query in [("ObjectId", {"workspaceId": TARGET_WORKSPACE}), ("string", {"workspaceId": "6a8d742a3a5477b2a74477a6"})]:
        docs = list(db["transactions"].find(query).limit(2))
        if docs:
            print(f"\n  First {len(docs)} transaction(s) (match by {label}):")
            for i, doc in enumerate(docs, 1):
                print(f"    --- Transaction {i} ---")
                print(f"    _id: {describe(doc.get('_id'))}")
                print(f"    workspaceId: {describe(doc.get('workspaceId'))}")
                for k, v in doc.items():
                    if k not in ("_id", "workspaceId"):
                        print(f"    {k}: {describe(v)}")
        else:
            print(f"  No transactions found with {label} workspaceId match")
    print()

    # ── 4. Other workspaces with transactions ─────────────────────────────
    print("-" * 70)
    print("4. TRANSACTIONS ACROSS ALL WORKSPACES")
    print("-" * 70)
    pipeline = [
        {"$group": {"_id": "$workspaceId", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    results = list(db["transactions"].aggregate(pipeline))
    if results:
        for r in results:
            marker = " <-- TARGET" if r["_id"] == TARGET_WORKSPACE else ""
            print(f"  workspaceId={describe(r['_id'])}  count={r['count']}{marker}")
    else:
        print("  No transactions found in any workspace")
    print()

    # ── 5. User details ───────────────────────────────────────────────────
    print("-" * 70)
    print("5. USER DETAILS (for membership holders)")
    print("-" * 70)
    for uid in user_ids:
        # Try ObjectId first, then string
        user = None
        if isinstance(uid, ObjectId):
            user = db["users"].find_one({"_id": uid})
        if not user and isinstance(uid, str):
            try:
                user = db["users"].find_one({"_id": ObjectId(uid)})
            except Exception:
                pass
        if not user:
            user = db["users"].find_one({"_id": uid})
        if user:
            print(f"\n  User _id: {describe(user.get('_id'))}")
            print(f"  email: {user.get('email', 'N/A')}")
            print(f"  name: {user.get('name', 'N/A')}")
            user_memberships = list(db["workspace_members"].find({"userId": user["_id"]}))
            print(f"  Memberships ({len(user_memberships)}):")
            for wm in user_memberships:
                print(f"    workspaceId={describe(wm.get('workspaceId'))}  role={wm.get('role')}  status={wm.get('status')}")
        else:
            print(f"\n  User with _id={describe(uid)} NOT FOUND in 'users' collection")
    print()

    # ── 6. Quick type audit ───────────────────────────────────────────────
    print("-" * 70)
    print("6. TYPE AUDIT: workspaceId in transactions")
    print("-" * 70)
    sample = list(db["transactions"].find().limit(5))
    if sample:
        types_seen = set()
        for doc in sample:
            wid = doc.get("workspaceId")
            types_seen.add(type(wid).__name__)
            print(f"  _id={describe(doc.get('_id'))}  workspaceId={describe(wid)}")
        print(f"  Distinct workspaceId types in sample: {types_seen}")
    else:
        print("  No transactions found to audit")
    print()

    print("=" * 70)
    print("DONE")
    print("=" * 70)
    client.close()


if __name__ == "__main__":
    run()
