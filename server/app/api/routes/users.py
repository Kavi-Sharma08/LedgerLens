from fastapi import APIRouter, Depends

from ...api.deps import get_current_user
from ...models.user import User
from ...schemas.user import UserPublic
from ...services.mappers import to_user_public

router = APIRouter()


@router.get("/me", response_model=UserPublic)
async def read_current_user(current_user: User = Depends(get_current_user)):
    """Returns the signed-in user. 401 when the session is missing or invalid."""
    return to_user_public(current_user)
