from fastapi import APIRouter

from src.api.v1 import auth, animal_types, pets


api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(animal_types.router)
api_router.include_router(pets.router)
