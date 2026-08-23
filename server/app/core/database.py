import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from .config import get_settings
from .errors import DatabaseUnavailableError

logger = logging.getLogger("ledgerlens.database")

INDEXES = [
    ("users", [("email", 1)], True),          # email must be unique per user
    ("workspaces", [("slug", 1)], True),      # slugs are addressable identifiers
    ("workspaces", [("owner_id", 1)], False),
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
    but data endpoints respond 503 until the connection succeeds."""
    settings = get_settings()

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


async def _ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    for collection, keys, unique in INDEXES:
        await db[collection].create_index(keys, unique=unique, background=True)


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
