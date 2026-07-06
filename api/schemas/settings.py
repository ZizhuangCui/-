# -*- coding: utf-8 -*-
from typing import Literal

from pydantic import BaseModel, Field


BroadcastFileType = Literal["daily_summary", "risk_comments", "raw_comments"]
BroadcastPeriodMode = Literal["crawl_cycle", "custom"]


class BroadcastSettings(BaseModel):
    enabled: bool = True
    feishu_group_name: str = "评论风险监控群"
    period_mode: BroadcastPeriodMode = "crawl_cycle"
    custom_interval_minutes: int = Field(default=60, ge=5, le=1440)
    selected_files: list[BroadcastFileType] = Field(
        default_factory=lambda: ["daily_summary", "risk_comments"]
    )


class BroadcastPreviewResponse(BaseModel):
    text: str
