from fastapi import APIRouter

from src.api.v1 import admin, animal_types, auth, pets


api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(animal_types.router)
api_router.include_router(pets.router)
api_router.include_router(admin.router)
