from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from ..core.errors import EmailAlreadyRegisteredError
from ..models.user import User

COLLECTION = "users"


async def get_by_email(db, email: str) -> User | None:
    doc = await db[COLLECTION].find_one({"email": email.lower()})
    return User.from_document(doc) if doc else None


async def get_by_id(db, user_id: str | ObjectId) -> User | None:
    try:
        _id = ObjectId(user_id)
    except Exception:
        return None
    doc = await db[COLLECTION].find_one({"_id": _id})
    return User.from_document(doc) if doc else None


async def create_user(db, user: User) -> User:
    """Insert a new user. The unique email index is the source of truth."""
    try:
        result = await db[COLLECTION].insert_one(user.to_document())
    except DuplicateKeyError:
        raise EmailAlreadyRegisteredError() from None
    user.id = result.inserted_id
    return user
