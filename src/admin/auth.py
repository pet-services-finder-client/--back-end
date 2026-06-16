from sqlalchemy import select
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from src.core.database import AsyncSessionLocal
from src.core.security import create_access_token, decode_token, verify_password
from src.models.user import User


class AdminAuth(AuthenticationBackend):
    """Authentication backend for sqladmin.

    Reuses the existing User model and password hashing.
    Only users with `is_admin=True` and `is_active=True` are allowed in.
    """

    async def login(self, request: Request) -> bool:
        """Called when the user submits the login form."""
        form = await request.form()
        email = form.get("username")
        password = form.get("password")

        if not email or not password:
            return False

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()

        if user is None:
            return False
        if not user.is_active or not user.is_admin:
            return False
        if not verify_password(password, user.hashed_password):
            return False

        # Issue a token and store it in the session
        token = create_access_token(subject=str(user.id))
        request.session.update({"token": token})
        return True

    async def logout(self, request: Request) -> bool:
        """Called when the user clicks 'Logout'."""
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        """Called on every request to admin pages to verify the session."""
        token = request.session.get("token")
        if not token:
            return False

        payload = decode_token(token)
        if payload is None or payload.get("type") != "access":
            return False

        user_id = payload.get("sub")
        if user_id is None:
            return False

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.id == int(user_id)))
            user = result.scalar_one_or_none()

        # Re-check is_admin on every request — in case admin was demoted
        if user is None or not user.is_active or not user.is_admin:
            return False

        return True
