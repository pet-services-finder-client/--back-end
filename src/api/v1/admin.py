from typing import Annotated

from fastapi import APIRouter, Depends

from src.core.deps import get_current_admin_user
from src.models.user import User
from src.schemas.user import UserRead


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/me", response_model=UserRead)
async def admin_whoami(
    current_admin: Annotated[User, Depends(get_current_admin_user)],
) -> User:
    """Verify admin access. Returns the admin's own profile if authorized."""
    return current_admin
