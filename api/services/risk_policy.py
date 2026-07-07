# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import List

from ..schemas import CrawlerStartRequest, MonitorIntervalEnum, MonitorJobRequest, PlatformEnum


XHS_MAX_NOTES_PER_RUN = 5
XHS_MAX_COMMENTS_PER_NOTE = 20
XHS_CRAWL_SLEEP_SECONDS = 12


def validate_crawler_risk_policy(config: CrawlerStartRequest) -> List[str]:
    """Return policy violations for platform behavior that should not run automatically."""
    if config.platform != PlatformEnum.XHS:
        return []

    issues: List[str] = []
    notes_count = config.max_notes_count or 15
    comments_count = config.max_comments_count or 10

    if config.headless:
        issues.append("小红书账号已有风控预警，暂不允许无头模式运行")
    if config.enable_sub_comments:
        issues.append("小红书账号已有风控预警，暂不允许采集二级评论")
    if notes_count > XHS_MAX_NOTES_PER_RUN:
        issues.append(f"小红书单次最多采集 {XHS_MAX_NOTES_PER_RUN} 篇笔记")
    if comments_count > XHS_MAX_COMMENTS_PER_NOTE:
        issues.append(f"小红书每篇最多采集 {XHS_MAX_COMMENTS_PER_NOTE} 条评论")

    return issues


def validate_monitor_risk_policy(request: MonitorJobRequest) -> List[str]:
    issues = validate_crawler_risk_policy(request.config)
    if request.platform != PlatformEnum.XHS:
        return issues

    if request.interval != MonitorIntervalEnum.DAILY:
        issues.append("小红书账号已有风控预警，自动监控频率只能设为每天一次")
    if request.run_immediately:
        issues.append("小红书账号已有风控预警，启用监控后不再立即执行首轮扫描")

    return issues
