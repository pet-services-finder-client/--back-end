from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.deps import get_current_active_user
from src.models.animal_type import AnimalType
from src.models.pet import Pet
from src.models.user import User
from src.schemas.pet import PetCreate, PetRead, PetUpdate


router = APIRouter(prefix="/pets", tags=["pets"])


async def _ensure_animal_type_exists(animal_type_id: int, db: AsyncSession) -> None:
    """Raise 422 if animal_type_id does not exist or is inactive."""
    result = await db.execute(
        select(AnimalType).where(
            AnimalType.id == animal_type_id,
            AnimalType.is_active == True,  # noqa: E712
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid animal_type_id",
        )


@router.post(
    "",
    response_model=PetRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_pet(
    pet_in: PetCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Pet:
    """Create a new pet owned by the authenticated user."""
    await _ensure_animal_type_exists(pet_in.animal_type_id, db)

    pet = Pet(**pet_in.model_dump(), owner_id=current_user.id)
    db.add(pet)
    await db.commit()
    await db.refresh(pet)
    return pet


@router.get("", response_model=list[PetRead])
async def list_my_pets(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[Pet]:
    """Return all pets owned by the authenticated user."""
    result = await db.execute(
        select(Pet)
        .where(Pet.owner_id == current_user.id)
        .order_by(Pet.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{pet_id}", response_model=PetRead)
async def get_pet(
    pet_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Pet:
    """Return a single pet by id. Only the owner can access it."""
    result = await db.execute(
        select(Pet).where(Pet.id == pet_id, Pet.owner_id == current_user.id)
    )
    pet = result.scalar_one_or_none()
    if pet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pet not found",
        )
    return pet


@router.patch("/{pet_id}", response_model=PetRead)
async def update_pet(
    pet_id: int,
    pet_in: PetUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Pet:
    """Partially update a pet. Only the owner can modify it."""
    result = await db.execute(
        select(Pet).where(Pet.id == pet_id, Pet.owner_id == current_user.id)
    )
    pet = result.scalar_one_or_none()
    if pet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pet not found",
        )

    update_data = pet_in.model_dump(exclude_unset=True)

    # If animal_type_id is being changed, verify the new value
    if "animal_type_id" in update_data:
        await _ensure_animal_type_exists(update_data["animal_type_id"], db)

    for field, value in update_data.items():
        setattr(pet, field, value)

    await db.commit()
    await db.refresh(pet)
    return pet


@router.delete("/{pet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pet(
    pet_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a pet. Only the owner can delete it."""
    result = await db.execute(
        select(Pet).where(Pet.id == pet_id, Pet.owner_id == current_user.id)
    )
    pet = result.scalar_one_or_none()
    if pet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pet not found",
        )

    await db.delete(pet)
    await db.commit()
