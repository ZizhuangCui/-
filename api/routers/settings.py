# -*- coding: utf-8 -*-
from fastapi import APIRouter

from ..schemas.settings import BroadcastPreviewResponse, BroadcastSettings
from ..services.broadcast_settings import broadcast_settings_service

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/broadcast", response_model=BroadcastSettings)
async def get_broadcast_settings():
    return broadcast_settings_service.get_settings()


@router.put("/broadcast", response_model=BroadcastSettings)
async def save_broadcast_settings(settings: BroadcastSettings):
    return broadcast_settings_service.save_settings(settings)


@router.post("/broadcast/preview", response_model=BroadcastPreviewResponse)
async def preview_broadcast(settings: BroadcastSettings):
    return {"text": broadcast_settings_service.preview_text(settings)}
