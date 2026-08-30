"""Self-healing degraded mode.

The FastAPI process used to connect to MongoDB exactly once at startup. Any
failure (e.g. a transient DNS/SRV or TLS blip resolving the Atlas URI) left
mongo.connected=False forever: /api/health reported degraded and every
database-backed endpoint 503'd — which the UI surfaced as "API degraded",
"No workspace", and "Access restricted" until the whole server was restarted.

These tests pin the new behavior: the watchdog keeps retrying connect_to_mongo
while disconnected, so a short outage recovers on its own, and it stays quiet
while connected so it never hammers the database.
"""

import asyncio

from app.core import database as db_module
import pytest


@pytest.mark.asyncio
async def test_watchdog_reconnects_after_transient_outage(monkeypatch):
    """The watchdog must recover the API after Mongo was unreachable at boot."""

    attempts = []

    def fake_connect():
        async def _inner():
            attempts.append(1)
            db_module.mongo.connected = True
            db_module.mongo.db = None
            return True
        return _inner()

    monkeypatch.setattr(db_module, "connect_to_mongo", fake_connect)

    db_module.mongo.connected = False
    task = asyncio.create_task(
        db_module.watch_database_connection(initial_delay=0, retry_interval=0.01)
    )
    await asyncio.sleep(0.15)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert attempts, "watchdog must retry connect_to_mongo while disconnected"
    assert db_module.mongo.connected

    # Restore a sane state so other tests that check mongo.connected see "online".
    db_module.mongo.connected = True
    db_module.mongo.db = None


@pytest.mark.asyncio
async def test_watchdog_stays_quiet_while_connected(monkeypatch):
    """Once connected the watchdog must not hammer Mongo with reconnect calls."""

    attempts = []

    def fake_connect():
        async def _inner():
            attempts.append(1)
            return True
        return _inner()

    monkeypatch.setattr(db_module, "connect_to_mongo", fake_connect)

    db_module.mongo.connected = True
    task = asyncio.create_task(
        db_module.watch_database_connection(initial_delay=0, retry_interval=0.01)
    )
    await asyncio.sleep(0.15)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert not attempts, "no reconnect attempts should happen while connected"

    db_module.mongo.connected = True
    db_module.mongo.db = None


@pytest.mark.asyncio
async def test_watchdog_survives_failed_reconnect_and_keeps_trying(monkeypatch):
    """A reconnect attempt that fails must not kill the watchdog — it keeps
    trying on the next interval."""

    attempts = []

    def failing_connect():
        async def _inner():
            attempts.append(1)
            db_module.mongo.connected = False
            return False
        return _inner()

    monkeypatch.setattr(db_module, "connect_to_mongo", failing_connect)

    db_module.mongo.connected = False
    task = asyncio.create_task(
        db_module.watch_database_connection(initial_delay=0, retry_interval=0.01)
    )
    await asyncio.sleep(0.15)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert len(attempts) >= 2, "watchdog must keep retrying after a failed attempt"

    db_module.mongo.connected = True
    db_module.mongo.db = None


def test_connect_to_mongo_is_idempotent(monkeypatch):
    """Re-invoking connect_to_mongo must close the previous client instead of
    leaking a second connection (the watchdog calls this repeatedly)."""

    closed = []

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.admin = self

        async def command(self, *args, **kwargs):
            return {"ok": 1}

        def __getitem__(self, name):
            return self

        def close(self):
            closed.append(1)

    monkeypatch.setattr(
        db_module, "AsyncIOMotorClient", lambda *a, **k: FakeClient()
    )

    async def fake_ensure_indexes(db):
        return None

    monkeypatch.setattr(db_module, "_ensure_indexes", fake_ensure_indexes)

    db_module.mongo.client = FakeClient()

    async def run():
        assert await db_module.connect_to_mongo() is True
        prev = db_module.mongo.client
        assert await db_module.connect_to_mongo() is True
        assert db_module.mongo.client is not prev
    asyncio.run(run())

    assert closed, "re-connect must close the stale client"

    db_module.mongo.client = None
    db_module.mongo.db = None
    db_module.mongo.connected = False