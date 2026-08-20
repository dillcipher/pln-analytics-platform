from __future__ import annotations

from fastapi import APIRouter

from app.application.registry.registry_service import RegistryService

router = APIRouter(
    prefix="/datasets",
    tags=["Datasets"],
)


@router.get("")
async def get_datasets():

    return RegistryService.get_registry()