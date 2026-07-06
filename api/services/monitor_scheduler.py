# -*- coding: utf-8 -*-
import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

from pydantic import ValidationError

from ..schemas import MonitorIntervalEnum, MonitorJobRequest, MonitorJobStatus, PlatformEnum
from .crawler_manager import crawler_manager


INTERVAL_SECONDS = {
    MonitorIntervalEnum.HOURLY: 60 * 60,
    MonitorIntervalEnum.TWICE_DAILY: 12 * 60 * 60,
    MonitorIntervalEnum.DAILY: 24 * 60 * 60,
}


def _now() -> datetime:
    return datetime.now()


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


class MonitorScheduler:
    """Persistent scheduler for comment risk monitoring jobs."""

    def __init__(self):
        self._project_root = Path(__file__).parent.parent.parent
        self._store_path = self._project_root / "config" / "monitor_jobs.local.json"
        self._lock = asyncio.Lock()
        self._jobs: Dict[str, MonitorJobStatus] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._started = False

    async def start(self):
        async with self._lock:
            if self._started:
                return
            self._load_jobs()
            self._started = True
            for platform, job in self._jobs.items():
                if job.enabled:
                    self._ensure_task(platform)

    async def stop(self):
        async with self._lock:
            self._started = False
            tasks = list(self._tasks.values())
            self._tasks = {}
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def enable_job(self, request: MonitorJobRequest) -> MonitorJobStatus:
        platform = request.platform.value
        next_run_at = _now() if request.run_immediately else _now() + self._interval_delta(request.interval)
        job = MonitorJobStatus(
            platform=platform,
            enabled=True,
            interval=request.interval,
            config=request.config,
            next_run_at=next_run_at.isoformat(timespec="seconds"),
            last_status="idle",
            last_error=None,
            running=False,
        )

        async with self._lock:
            old_job = self._jobs.get(platform)
            if old_job:
                job.last_run_at = old_job.last_run_at
                job.last_finished_at = old_job.last_finished_at
                job.last_status = old_job.last_status if old_job.last_status != "running" else "idle"
                job.last_error = old_job.last_error
            self._jobs[platform] = job
            self._save_jobs()
            self._ensure_task(platform)
            return job

    async def disable_job(self, platform: PlatformEnum) -> MonitorJobStatus:
        platform_key = platform.value
        async with self._lock:
            job = self._jobs.get(platform_key)
            if not job:
                job = MonitorJobStatus(platform=platform_key, enabled=False)
                self._jobs[platform_key] = job
            else:
                job.enabled = False
                job.running = False
                job.next_run_at = None
                if job.last_status == "running":
                    job.last_status = "idle"
            task = self._tasks.pop(platform_key, None)
            self._save_jobs()

        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        return job

    async def get_jobs(self) -> list[MonitorJobStatus]:
        async with self._lock:
            return [self._copy_job(job) for job in self._jobs.values()]

    async def get_job(self, platform: PlatformEnum) -> MonitorJobStatus:
        platform_key = platform.value
        async with self._lock:
            job = self._jobs.get(platform_key)
            if not job:
                return MonitorJobStatus(platform=platform_key, enabled=False)
            return self._copy_job(job)

    def _ensure_task(self, platform: str):
        if not self._started:
            return
        task = self._tasks.get(platform)
        if task and not task.done():
            return
        self._tasks[platform] = asyncio.create_task(self._run_loop(platform))

    async def _run_loop(self, platform: str):
        try:
            while True:
                async with self._lock:
                    job = self._jobs.get(platform)
                    if not job or not job.enabled or not job.config:
                        return
                    next_run_at = _parse_dt(job.next_run_at) or _now()

                delay = max((next_run_at - _now()).total_seconds(), 0)
                if delay:
                    await asyncio.sleep(min(delay, 60))
                    continue

                await self._run_job(platform)
        except asyncio.CancelledError:
            return

    async def _run_job(self, platform: str):
        async with self._lock:
            job = self._jobs.get(platform)
            if not job or not job.enabled or not job.config:
                return
            job.running = True
            job.last_status = "running"
            job.last_run_at = _now().isoformat(timespec="seconds")
            job.last_error = None
            self._save_jobs()
            config = job.config
            interval = job.interval

        try:
            while crawler_manager.process and crawler_manager.process.poll() is None:
                await asyncio.sleep(15)

            started = await crawler_manager.start(config)
            if not started:
                raise RuntimeError("crawler is busy or failed to start")

            while crawler_manager.process and crawler_manager.process.poll() is None:
                await asyncio.sleep(2)
            while crawler_manager.status == "running":
                await asyncio.sleep(1)

            exit_code = crawler_manager.last_exit_code
            if exit_code == 0:
                last_status = "success"
                last_error = None
            else:
                last_status = "failed"
                last_error = f"crawler exited with code {exit_code}"
        except Exception as exc:
            last_status = "failed"
            last_error = str(exc)

        async with self._lock:
            job = self._jobs.get(platform)
            if not job:
                return
            job.running = False
            job.last_finished_at = _now().isoformat(timespec="seconds")
            job.last_status = last_status
            job.last_error = last_error
            if job.enabled:
                job.next_run_at = (_now() + self._interval_delta(interval)).isoformat(timespec="seconds")
            else:
                job.next_run_at = None
            self._save_jobs()

    def _interval_delta(self, interval: MonitorIntervalEnum) -> timedelta:
        return timedelta(seconds=INTERVAL_SECONDS[interval])

    def _load_jobs(self):
        if not self._store_path.exists():
            self._jobs = {}
            return

        try:
            payload = json.loads(self._store_path.read_text(encoding="utf-8"))
            jobs = payload.get("jobs", [])
            loaded: Dict[str, MonitorJobStatus] = {}
            for item in jobs:
                try:
                    job = MonitorJobStatus.model_validate(item)
                except ValidationError:
                    continue
                if job.enabled and job.next_run_at:
                    next_run_at = _parse_dt(job.next_run_at)
                    if next_run_at and next_run_at < _now():
                        job.next_run_at = _now().isoformat(timespec="seconds")
                loaded[job.platform] = job
            self._jobs = loaded
        except (OSError, json.JSONDecodeError):
            self._jobs = {}

    def _save_jobs(self):
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "updated_at": _now().isoformat(timespec="seconds"),
            "jobs": [job.model_dump(mode="json") for job in self._jobs.values()],
        }
        self._store_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _copy_job(self, job: MonitorJobStatus) -> MonitorJobStatus:
        return MonitorJobStatus.model_validate(job.model_dump(mode="json"))


monitor_scheduler = MonitorScheduler()
