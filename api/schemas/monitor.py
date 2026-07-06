# -*- coding: utf-8 -*-
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel

from .crawler import CrawlerStartRequest, PlatformEnum


class MonitorIntervalEnum(str, Enum):
    """Supported recurring monitor intervals."""

    HOURLY = "hourly"
    TWICE_DAILY = "twice_daily"
    DAILY = "daily"


class MonitorJobRequest(BaseModel):
    """Request to enable or update a monitor job."""

    platform: PlatformEnum
    interval: MonitorIntervalEnum = MonitorIntervalEnum.HOURLY
    config: CrawlerStartRequest
    run_immediately: bool = True


class MonitorJobStatus(BaseModel):
    """Current persisted and runtime state for a monitor job."""

    platform: str
    enabled: bool = False
    interval: MonitorIntervalEnum = MonitorIntervalEnum.HOURLY
    config: Optional[CrawlerStartRequest] = None
    next_run_at: Optional[str] = None
    last_run_at: Optional[str] = None
    last_finished_at: Optional[str] = None
    last_status: Literal["idle", "running", "success", "failed", "skipped"] = "idle"
    last_error: Optional[str] = None
    running: bool = False


class MonitorJobsResponse(BaseModel):
    jobs: list[MonitorJobStatus]
