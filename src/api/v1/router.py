from fastapi import APIRouter

from src.api.v1 import auth


api_router = APIRouter()
api_router.include_router(auth.router)
