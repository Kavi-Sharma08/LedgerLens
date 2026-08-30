import asyncio
import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from .config import get_settings
from .errors import DatabaseUnavailableError
from ..models.enums import FileStatus

logger = logging.getLogger("ledgerlens.database")

# How long the reconnect watchdog waits before its first attempt and between
# attempts. Kept long enough to ride out transient DNS/TLS blips without
# hammering an unreachable host.
WATCHDOG_INITIAL_DELAY = 5.0
WATCHDOG_RETRY_INTERVAL = 15.0

INDEXES = [
    # --- existing auth/workspace foundation ---
    ("users", [("email", 1)], True),          # email must be unique per user
    ("workspaces", [("slug", 1)], True),      # slugs are addressable identifiers
    ("workspaces", [("ownerId", 1)], False),  # matches the camelCase document field
    # --- workspace membership (Phase 3) ---
    ("workspace_members", [("workspaceId", 1), ("userId", 1)], True),  # one membership per user/workspace
    ("workspace_members", [("userId", 1)], False),                     # "all my workspaces" lookup
    ("workspace_members", [("workspaceId", 1), ("role", 1)], False),  # role-based queries
    # --- financial data (Phase 2) ---
    # Every financial index leads with workspaceId: all queries are
    # tenant-scoped first, so isolation is reflected in the index layout.
    ("sources", [("workspaceId", 1), ("name", 1)], True),   # unique name/tenant + listing
    ("sources", [("workspaceId", 1), ("type", 1)], False),  # filter by source type
    # File-level idempotency: exactly ONE primary copy of identical import
    # content per source. Partial: re-upload attempts recorded with status
    # DUPLICATE must not collide with the primary copy they point to.
    # NOTE: MongoDB partialFilterExpression does NOT support $ne, so "every
    # status except DUPLICATE" is expressed as the explicit $in list below,
    # derived from FileStatus so the two can never drift apart.
    (
        "source_files",
        [("workspaceId", 1), ("sourceId", 1), ("checksum", 1)],
        True,
        {"status": {"$in": [s.value for s in FileStatus if s is not FileStatus.DUPLICATE]}},
    ),
    # "Files of this source, newest first" screens.
    ("source_files", [("workspaceId", 1), ("sourceId", 1), ("uploadedAt", -1)], False),
    # Evidence-level idempotency: replayed records cannot duplicate evidence.
    ("raw_transactions", [("workspaceId", 1), ("sourceId", 1), ("recordHash", 1)], True),
    # Reprocessing / debugging per imported file.
    ("raw_transactions", [("workspaceId", 1), ("sourceFileId", 1)], False),
    # Duplicate-content detection during ingestion.
    ("transactions", [("workspaceId", 1), ("sourceId", 1), ("fingerprint", 1)], False),
    # Date-range filters and reconciliation run scoping.
    ("transactions", [("workspaceId", 1), ("transactionDate", -1)], False),
    # Amount-blocked candidate lookups within one currency.
    ("transactions", [("workspaceId", 1), ("currency", 1), ("amount", 1)], False),
    # Trace a source-system record id to its canonical transaction.
    ("transactions", [("workspaceId", 1), ("sourceRecordId", 1)], False),
    # Run history, newest first.
    ("reconciliation_runs", [("workspaceId", 1), ("startedAt", -1)], False),
    # Candidate retrieval is always run-scoped.
    ("match_candidates", [("reconciliationRunId", 1)], False),
    # Results pages and review queues.
    ("matches", [("workspaceId", 1), ("reconciliationRunId", 1)], False),
    ("exceptions", [("workspaceId", 1), ("reconciliationRunId", 1)], False),
    ("exceptions", [("workspaceId", 1), ("status", 1)], False),
    # --- audit logs (Phase 9) ---
    ("audit_logs", [("workspaceId", 1), ("createdAt", -1)], False),
    ("audit_logs", [("workspaceId", 1), ("action", 1), ("createdAt", -1)], False),
    # --- invitations ---
    (
        "invitations",
        [("workspaceId", 1), ("email", 1), ("status", 1)],
        True,
        {"status": "PENDING"},
    ),
    ("invitations", [("tokenHash", 1)], False),
    ("invitations", [("expiresAt", 1)], False),
]


class MongoState:
    """Holds the shared Motor client and tracks connectivity."""

    def __init__(self):
        self.client: AsyncIOMotorClient | None = None
        self.db: AsyncIOMotorDatabase | None = None
        self.connected: bool = False


mongo = MongoState()


async def connect_to_mongo() -> bool:
    """Connect to MongoDB. The API starts even if the database is unreachable,
    but data endpoints respond 503 until the connection succeeds.

    Safe to call repeatedly: any stale client from a previous attempt is closed
    so the watchdog's reconnect attempts never leak connections."""
    settings = get_settings()

    if mongo.client is not None:
        mongo.client.close()
        mongo.client = None
    mongo.db = None
    mongo.connected = False

    mongo.client = AsyncIOMotorClient(settings.mongodb_uri, serverSelectionTimeoutMS=3000)
    try:
        await mongo.client.admin.command("ping")
        mongo.db = mongo.client[settings.mongodb_database]
        await _ensure_indexes(mongo.db)
        mongo.connected = True
        logger.info("MongoDB connected (database=%s)", settings.mongodb_database)
        return True
    except Exception as exc:  # noqa: BLE001 - fail gracefully by design
        mongo.connected = False
        logger.warning("MongoDB unavailable, running in degraded mode: %s", exc)
        return False


async def watch_database_connection(
    *,
    initial_delay: float = WATCHDOG_INITIAL_DELAY,
    retry_interval: float = WATCHDOG_RETRY_INTERVAL,
) -> None:
    """Background task that makes degraded mode self-healing.

    connect_to_mongo runs exactly once at startup; any failure (including a
    transient DNS/SRV or TLS hiccup against the configured URI) flipped the
    API into degraded mode FOREVER — /api/health reported "degraded" and every
    database endpoint 503'd until the process was restarted. That one-shot
    behavior is why a brief MongoDB outage after a restart presented as a
    persistent "workspace disappeared" regression.

    This task keeps retrying connect_to_mongo whenever mongo.connected is
    False, so a transient outage now recovers without any restart.
    """
    try:
        await asyncio.sleep(initial_delay)
    except asyncio.CancelledError:
        return
    while True:
        await asyncio.sleep(retry_interval)
        if mongo.connected:
            continue
        logger.warning("MongoDB unavailable — retrying connection…")
        try:
            await connect_to_mongo()
        except asyncio.CancelledError:
            return
        except Exception:  # noqa: BLE001
            logger.warning("MongoDB reconnect attempt failed", exc_info=True)


async def _ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    for entry in INDEXES:
        collection, keys, unique = entry[0], entry[1], entry[2]
        kwargs = {"unique": unique, "background": True}
        if len(entry) > 3 and entry[3]:
            kwargs["partialFilterExpression"] = entry[3]
        await db[collection].create_index(keys, **kwargs)


async def close_mongo() -> None:
    if mongo.client is not None:
        mongo.client.close()
        mongo.connected = False
        logger.info("MongoDB connection closed")


def get_database() -> AsyncIOMotorDatabase:
    """FastAPI dependency. Raises DatabaseUnavailableError when degraded."""
    if not mongo.connected or mongo.db is None:
        raise DatabaseUnavailableError()
    return mongo.db
