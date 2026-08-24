"""Load the deterministic synthetic dataset through the REAL ingestion pipeline.

Usage:
    venv/Scripts/python scripts/seed_synthetic.py                 # seed MongoDB
    venv/Scripts/python scripts/seed_synthetic.py --dump-ground-truth

Creates a development workspace, three sources and ingests every scenario
through upload_source_file (extraction -> normalization -> fingerprint ->
persistence), so seeded data exercises exactly what production will."""

import argparse
import asyncio
import csv
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import _ensure_indexes, close_mongo, connect_to_mongo, mongo  # noqa: E402
from app.models.enums import SourceType  # noqa: E402
from app.models.source import Source  # noqa: E402
from app.repositories.source_repository import create_source  # noqa: E402
from app.services.source_service import upload_source_file  # noqa: E402
from app.synthetic.dataset import (  # noqa: E402
    ACCOUNTING,
    BANK,
    GATEWAY,
    SOURCE_NAMES,
    records_for_source,
)
from app.synthetic.ground_truth import GROUND_TRUTH  # noqa: E402


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


async def seed() -> dict:
    connected = await connect_to_mongo()
    if not connected:
        print("MongoDB is not reachable. Start it and retry.")
        sys.exit(1)

    db = mongo.db
    await _ensure_indexes(db)

    from bson import ObjectId

    from app.models.workspace import Workspace
    from app.repositories.source_repository import list_sources
    from app.repositories.workspace_repository import create_workspace, first_for_owner

    owner_id = ObjectId("0000000000000000000000aa")
    workspace = await first_for_owner(db, str(owner_id))
    if workspace is None:
        workspace = Workspace(
            name="Synthetic Reconciliation Co.",
            slug="synthetic-reconciliation",
            owner_id=owner_id,
        )
        workspace = await create_workspace(db, workspace)
        print(f"workspace created: {workspace.id}")

    source_ids = {}
    for key in (BANK, GATEWAY, ACCOUNTING):
        name, type_name = SOURCE_NAMES[key]
        page = await list_sources(db, workspace.id, limit=200)
        match = next((s for s in page.items if s.name == name), None)
        if match:
            source_ids[key] = match.id
            print(f"source exists: {name} -> {match.id}")
            continue
        source = await create_source(
            db,
            workspace.id,
            Source(workspace_id=workspace.id, name=name, type=SourceType(type_name), currency="INR"),
        )
        source_ids[key] = source.id
        print(f"source created: {name} -> {source.id}")

    totals = {}
    from app.repositories.source_repository import get_by_id

    for key in (BANK, GATEWAY, ACCOUNTING):
        records = records_for_source(key)
        content = build_csv(records)
        source = await get_by_id(db, workspace.id, source_ids[key])
        summary = await upload_source_file(
            db, workspace.id,
            source=source,
            file_name=f"synthetic_{key.lower()}_aug_2026.csv",
            mime_type="text/csv",
            content=content,
            uploaded_by=None,
        )
        totals[key] = summary
        print(
            f"{key}: processed={summary.processed_count} "
            f"skippedDuplicates={summary.skipped_duplicate_count} errors={summary.error_count}"
        )

    await close_mongo()
    return {"workspace": str(workspace.id), **{k: v.processed_count for k, v in totals.items()}}


def dump_ground_truth(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "description": "Expected reconciliation outcomes for the deterministic synthetic dataset.",
        "entries": GROUND_TRUTH,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"ground truth written: {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed LedgerLens synthetic dataset.")
    parser.add_argument("--dump-ground-truth", action="store_true")
    args = parser.parse_args()

    if args.dump_ground_truth:
        dump_ground_truth(Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "synthetic_ground_truth.json")
    else:
        result = asyncio.run(seed())
        print(json.dumps(result, indent=2))
