# -*- coding: utf-8 -*-
from fastapi import APIRouter

from ..schemas import MonitorJobRequest, MonitorJobStatus, MonitorJobsResponse, PlatformEnum
from ..services import monitor_scheduler

router = APIRouter(prefix="/monitor", tags=["monitor"])


@router.get("/jobs", response_model=MonitorJobsResponse)
async def get_monitor_jobs():
    return {"jobs": await monitor_scheduler.get_jobs()}


@router.get("/jobs/{platform}", response_model=MonitorJobStatus)
async def get_monitor_job(platform: PlatformEnum):
    return await monitor_scheduler.get_job(platform)


@router.post("/jobs/{platform}/enable", response_model=MonitorJobStatus)
async def enable_monitor_job(platform: PlatformEnum, request: MonitorJobRequest):
    request.platform = platform
    request.config.platform = platform
    return await monitor_scheduler.enable_job(request)


@router.post("/jobs/{platform}/disable", response_model=MonitorJobStatus)
async def disable_monitor_job(platform: PlatformEnum):
    return await monitor_scheduler.disable_job(platform)
