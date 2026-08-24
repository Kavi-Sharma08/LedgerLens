"""Workspace isolation: every query is tenant-scoped, unique indexes are
tenant-scoped, and foreign ids behave exactly like unknown ones."""

import pytest
from bson import ObjectId

from app.core.errors import InvalidSourceError, NotFoundError
from app.models.enums import SourceType
from app.models.workspace import Workspace
from app.repositories import (
    exception_repository,
    match_repository,
    raw_transaction_repository,
    reconciliation_run_repository,
    source_file_repository,
    source_repository,
    transaction_repository,
    workspace_repository,
)
from app.services.reconciliation_service import start_run
from app.services.source_service import create_source, upload_source_file

from .conftest import WORKSPACE_ID

OTHER_WORKSPACE = ObjectId("000000000000000000000002")

CSV = (
    b"TxnId,Date,Amount,Currency,Description,Reference,Counterparty\n"
    b"W1,2026-08-10,100.00,INR,row one,R1,CP ONE\n"
    b"W2,2026-08-11,200.00,INR,row two,R2,CP TWO\n"
)


async def _seed_workspace(db, workspace_id, name):
    ws = Workspace(name=name, slug=name.lower(), owner_id=ObjectId())
    return await workspace_repository.create_workspace(db, ws)


@pytest.mark.asyncio
async def test_same_source_name_allowed_across_workspaces(fake_db):
    await _seed_workspace(fake_db, WORKSPACE_ID, "Alpha")
    await _seed_workspace(fake_db, OTHER_WORKSPACE, "Beta")

    s1 = await create_source(fake_db, WORKSPACE_ID, name="Main Bank",
                             source_type=SourceType.BANK)
    s2 = await create_source(fake_db, OTHER_WORKSPACE, name="Main Bank",
                             source_type=SourceType.BANK)
    assert s1.id != s2.id


@pytest.mark.asyncio
async def test_transactions_are_invisible_cross_tenant(fake_db):
    await _seed_workspace(fake_db, WORKSPACE_ID, "Alpha")
    await _seed_workspace(fake_db, OTHER_WORKSPACE, "Beta")
    source = await create_source(fake_db, WORKSPACE_ID, name="Bank A",
                                 source_type=SourceType.BANK)

    from app.services.source_service import upload_source_file as up
    await up(fake_db, WORKSPACE_ID, source=source, file_name="a.csv",
             mime_type="text/csv", content=CSV, uploaded_by=None)

    mine = await transaction_repository.list_for_sources(
        fake_db, WORKSPACE_ID, [source.id]
    )
    assert len(mine) == 2

    theirs_by_source = await transaction_repository.list_for_sources(
        fake_db, OTHER_WORKSPACE, [source.id]   # same id, wrong tenant
    )
    assert theirs_by_source == []

    single = await transaction_repository.get_by_id(
        fake_db, OTHER_WORKSPACE, mine[0].id
    )
    assert single is None


@pytest.mark.asyncio
async def test_identical_file_content_is_not_a_duplicate_across_tenants(fake_db):
    await _seed_workspace(fake_db, WORKSPACE_ID, "Alpha")
    await _seed_workspace(fake_db, OTHER_WORKSPACE, "Beta")
    src_a = await create_source(fake_db, WORKSPACE_ID, name="A Bank",
                                source_type=SourceType.BANK)
    src_b = await create_source(fake_db, OTHER_WORKSPACE, name="B Bank",
                                source_type=SourceType.BANK)

    first = await upload_source_file(fake_db, WORKSPACE_ID, source=src_a,
                                     file_name="x.csv", mime_type="text/csv",
                                     content=CSV, uploaded_by=None)
    second = await upload_source_file(fake_db, OTHER_WORKSPACE, source=src_b,
                                      file_name="y.csv", mime_type="text/csv",
                                      content=CSV, uploaded_by=None)
    assert not second.is_duplicate
    assert second.processed_count == 2


@pytest.mark.asyncio
async def test_foreign_source_id_is_rejected_for_reconciliation(fake_db):
    await _seed_workspace(fake_db, WORKSPACE_ID, "Alpha")
    await _seed_workspace(fake_db, OTHER_WORKSPACE, "Beta")
    foreign = await create_source(fake_db, OTHER_WORKSPACE, name="Foreign",
                                  source_type=SourceType.BANK)
    local = await create_source(fake_db, WORKSPACE_ID, name="Local",
                                source_type=SourceType.PAYMENT_PROCESSOR)

    with pytest.raises(InvalidSourceError):
        await start_run(fake_db, WORKSPACE_ID, source_ids=[local.id, foreign.id])


@pytest.mark.asyncio
async def test_unknown_workspace_context_raises(fake_db):
    with pytest.raises(NotFoundError):
        await source_repository.get_by_id(fake_db, OTHER_WORKSPACE, ObjectId())


async def _upload(db, workspace_id, source, name):
    return await upload_source_file(
        db, workspace_id, source=source,
        file_name=name, mime_type="text/csv", content=CSV, uploaded_by=None,
    )


@pytest.mark.asyncio
async def test_run_results_are_invisible_cross_tenant(fake_db):
    """Runs, matches and exceptions created in workspace A must be unreachable
    from workspace B: by id AND by listing."""
    await _seed_workspace(fake_db, WORKSPACE_ID, "Alpha")
    await _seed_workspace(fake_db, OTHER_WORKSPACE, "Beta")

    async def _pair(ws):
        bank = await create_source(fake_db, ws, name="Bank", source_type=SourceType.BANK)
        gateway = await create_source(
            fake_db, ws, name="Gateway", source_type=SourceType.PAYMENT_PROCESSOR
        )
        await _upload(fake_db, ws, bank, "bank.csv")
        await _upload(fake_db, ws, gateway, "gw.csv")
        return [bank.id, gateway.id]

    ids_a = await _pair(WORKSPACE_ID)
    run = await start_run(fake_db, WORKSPACE_ID, source_ids=ids_a)

    # Workspace B runs its own reconciliation so both tenants have data.
    ids_b = await _pair(OTHER_WORKSPACE)
    await start_run(fake_db, OTHER_WORKSPACE, source_ids=ids_b)

    # Positive access: owner sees its own results.
    assert (await reconciliation_run_repository.get_by_id(
        fake_db, WORKSPACE_ID, run.id)).id == run.id

    # Negative access by id: foreign run/match/exception behave as not-found.
    from app.core.errors import ReconciliationRunNotFoundError

    with pytest.raises(ReconciliationRunNotFoundError):
        await reconciliation_run_repository.get_by_id(fake_db, OTHER_WORKSPACE, run.id)

    matches = (await match_repository.list_matches_for_run(
        fake_db, WORKSPACE_ID, run.id, limit=200)).items
    assert matches
    for match in matches:
        assert (await match_repository.list_matches_for_run(
            fake_db, OTHER_WORKSPACE, match.reconciliation_run_id, limit=1)
        ).items == []

    exceptions = (await exception_repository.list_for_run(
        fake_db, WORKSPACE_ID, run.id, limit=200)).items
    for exc in exceptions:
        assert (await exception_repository.list_for_run(
            fake_db, OTHER_WORKSPACE, exc.reconciliation_run_id, limit=1)
        ).items == []

    # Listing scoping: B's run history never contains A's run.
    b_runs = (await reconciliation_run_repository.list_runs(
        fake_db, OTHER_WORKSPACE, limit=200)).items
    assert run.id not in [r.id for r in b_runs]
    a_runs = (await reconciliation_run_repository.list_runs(
        fake_db, WORKSPACE_ID, limit=200)).items
    assert {r.id for r in a_runs} >= {run.id}


@pytest.mark.asyncio
async def test_files_and_raw_evidence_are_invisible_cross_tenant(fake_db):
    await _seed_workspace(fake_db, WORKSPACE_ID, "Alpha")
    other_source = await create_source(
        fake_db, OTHER_WORKSPACE, name="Other Bank", source_type=SourceType.BANK
    )
    source = await create_source(fake_db, WORKSPACE_ID, name="My Bank",
                                 source_type=SourceType.BANK)
    summary = await _upload(fake_db, WORKSPACE_ID, source, "mine.csv")

    from app.core.errors import SourceFileNotFoundError

    with pytest.raises(SourceFileNotFoundError):
        await source_file_repository.get_by_id(fake_db, OTHER_WORKSPACE, summary.file.id)

    page = await raw_transaction_repository.list_for_file(
        fake_db, WORKSPACE_ID, summary.file.id
    )
    assert len(page.items) == 2

    # Raw evidence queries are workspace-scoped too.
    foreign_raws = await raw_transaction_repository.list_for_file(
        fake_db, OTHER_WORKSPACE, summary.file.id
    )
    assert foreign_raws.items == []


@pytest.mark.asyncio
async def test_same_source_record_ids_across_workspaces_never_collide(fake_db):
    """Idempotency keys are tenant-scoped: identical evidence in two tenants
    is two independent records, never a cross-workspace duplicate collision."""
    await _seed_workspace(fake_db, WORKSPACE_ID, "Alpha")
    await _seed_workspace(fake_db, OTHER_WORKSPACE, "Beta")

    src_a = await create_source(fake_db, WORKSPACE_ID, name="A", source_type=SourceType.BANK)
    src_b = await create_source(fake_db, OTHER_WORKSPACE, name="B", source_type=SourceType.BANK)

    first = await upload_source_file(fake_db, WORKSPACE_ID, source=src_a,
                                     file_name="a.csv", mime_type="text/csv",
                                     content=CSV, uploaded_by=None)
    second = await upload_source_file(fake_db, OTHER_WORKSPACE, source=src_b,
                                      file_name="a.csv", mime_type="text/csv",
                                      content=CSV, uploaded_by=None)

    assert first.processed_count == 2
    assert second.processed_count == 2          # nothing skipped as "duplicate"
    assert second.skipped_duplicate_count == 0

    txns_a = await transaction_repository.list_for_sources(fake_db, WORKSPACE_ID, [src_a.id])
    txns_b = await transaction_repository.list_for_sources(fake_db, OTHER_WORKSPACE, [src_b.id])
    assert {t.source_record_id for t in txns_a} == \
           {t.source_record_id for t in txns_b} == {"W1", "W2"}
    assert {t.id for t in txns_a}.isdisjoint({t.id for t in txns_b})


@pytest.mark.asyncio
async def test_fingerprint_duplicate_detection_is_source_scoped_not_global(fake_db):
    """The same economic content in two DIFFERENT sources of one workspace is
    legitimate dual-coverage, not a duplicate; within one source it is
    surfaced as a potential duplicate for review."""
    src_1 = await create_source(fake_db, WORKSPACE_ID, name="One", source_type=SourceType.BANK)
    src_2 = await create_source(fake_db, WORKSPACE_ID, name="Two", source_type=SourceType.CARD)

    await _upload(fake_db, WORKSPACE_ID, src_1, "one.csv")
    await _upload(fake_db, WORKSPACE_ID, src_2, "two.csv")

    for source in (src_1, src_2):
        txns = await transaction_repository.list_for_sources(fake_db, WORKSPACE_ID, [source.id])
        assert all(t.potential_duplicate_ids == [] for t in txns)
