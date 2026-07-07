# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/api/services/crawler_manager.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。

import asyncio
import base64
import csv
import hashlib
import hmac
import subprocess
import signal
import os
import re
import sys
import time
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path

import httpx

from ..schemas import CrawlerStartRequest, LoginStartRequest, LogEntry
from .comment_report import comment_report_service
from .feishu_sheet_sync import feishu_sheet_sync_service
from .broadcast_settings import broadcast_settings_service
from .risk_policy import XHS_CRAWL_SLEEP_SECONDS


PLATFORM_DATA_DIRS = {
    "xhs": "xhs",
    "dy": "douyin",
    "bili": "bili",
}


class CrawlerManager:
    """Crawler process manager"""

    def __init__(self):
        self._lock = asyncio.Lock()
        self.process: Optional[subprocess.Popen] = None
        self.status = "idle"
        self.started_at: Optional[datetime] = None
        self.current_config: Optional[CrawlerStartRequest] = None
        self.last_exit_code: Optional[int] = None
        self._log_id = 0
        self._logs: List[LogEntry] = []
        self._read_task: Optional[asyncio.Task] = None
        self.login_processes: Dict[str, subprocess.Popen] = {}
        self.login_states: Dict[str, Dict[str, Any]] = {}
        self._login_read_tasks: Dict[str, asyncio.Task] = {}
        # Project root directory
        self._project_root = Path(__file__).parent.parent.parent
        # Log queue - for pushing to WebSocket
        self._log_queue: Optional[asyncio.Queue] = None

    @property
    def logs(self) -> List[LogEntry]:
        return self._logs

    def get_log_queue(self) -> asyncio.Queue:
        """Get or create log queue"""
        if self._log_queue is None:
            self._log_queue = asyncio.Queue()
        return self._log_queue

    def _create_log_entry(self, message: str, level: str = "info") -> LogEntry:
        """Create log entry"""
        self._log_id += 1
        entry = LogEntry(
            id=self._log_id,
            timestamp=datetime.now().strftime("%H:%M:%S"),
            level=level,
            message=message
        )
        self._logs.append(entry)
        # Keep last 500 logs
        if len(self._logs) > 500:
            self._logs = self._logs[-500:]
        return entry

    async def _push_log(self, entry: LogEntry):
        """Push log to queue"""
        if self._log_queue is not None:
            try:
                self._log_queue.put_nowait(entry)
            except asyncio.QueueFull:
                pass

    def _parse_log_level(self, line: str) -> str:
        """Parse log level"""
        line_upper = line.upper()
        if "ERROR" in line_upper or "FAILED" in line_upper:
            return "error"
        elif "WARNING" in line_upper or "WARN" in line_upper:
            return "warning"
        elif "SUCCESS" in line_upper or "完成" in line or "成功" in line:
            return "success"
        elif "DEBUG" in line_upper:
            return "debug"
        return "info"

    async def start(self, config: CrawlerStartRequest) -> bool:
        """Start crawler process"""
        async with self._lock:
            if self.process and self.process.poll() is None:
                return False

            # Clear old logs
            self._logs = []
            self._log_id = 0

            # Clear pending queue (don't replace object to avoid WebSocket broadcast coroutine holding old queue reference)
            if self._log_queue is None:
                self._log_queue = asyncio.Queue()
            else:
                try:
                    while True:
                        self._log_queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass

            # Build command line arguments
            cmd = self._build_command(config)

            # Log start information
            entry = self._create_log_entry(f"Starting crawler: {' '.join(cmd)}", "info")
            await self._push_log(entry)

            try:
                # Start subprocess
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding='utf-8',
                    bufsize=1,
                    cwd=str(self._project_root),
                    env={**os.environ, "PYTHONUNBUFFERED": "1"}
                )

                self.status = "running"
                self.started_at = datetime.now()
                self.current_config = config
                self.last_exit_code = None

                entry = self._create_log_entry(
                    f"Crawler started on platform: {config.platform.value}, type: {config.crawler_type.value}",
                    "success"
                )
                await self._push_log(entry)

                # Start log reading task
                self._read_task = asyncio.create_task(self._read_output())

                return True
            except Exception as e:
                self.status = "error"
                entry = self._create_log_entry(f"Failed to start crawler: {str(e)}", "error")
                await self._push_log(entry)
                return False

    async def stop(self) -> bool:
        """Stop crawler process"""
        async with self._lock:
            if not self.process or self.process.poll() is not None:
                return False

            self.status = "stopping"
            entry = self._create_log_entry("Sending SIGTERM to crawler process...", "warning")
            await self._push_log(entry)

            try:
                self.process.send_signal(signal.SIGTERM)

                # Wait for graceful exit (up to 15 seconds)
                for _ in range(30):
                    if self.process.poll() is not None:
                        break
                    await asyncio.sleep(0.5)

                # If still not exited, force kill
                if self.process.poll() is None:
                    entry = self._create_log_entry("Process not responding, sending SIGKILL...", "warning")
                    await self._push_log(entry)
                    self.process.kill()

                entry = self._create_log_entry("Crawler process terminated", "info")
                await self._push_log(entry)

            except Exception as e:
                entry = self._create_log_entry(f"Error stopping crawler: {str(e)}", "error")
                await self._push_log(entry)

            self.status = "idle"
            self.current_config = None

            # Cancel log reading task
            if self._read_task:
                self._read_task.cancel()
                self._read_task = None

            return True

    async def start_login(self, config: LoginStartRequest) -> bool:
        """Start a platform login-only process"""
        async with self._lock:
            platform = config.platform.value
            existing_process = self.login_processes.get(platform)
            if existing_process and existing_process.poll() is None:
                return False

            if self.process and self.process.poll() is None:
                return False

            cmd = self._build_login_command(config)
            now = datetime.now()
            self.login_states[platform] = {
                "status": "running",
                "started_at": now,
                "finished_at": None,
                "error_message": None,
            }

            entry = self._create_log_entry(f"Starting {platform} login setup: {' '.join(cmd)}", "info")
            await self._push_log(entry)

            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    bufsize=1,
                    cwd=str(self._project_root),
                    env={**os.environ, "PYTHONUNBUFFERED": "1"},
                )
                self.login_processes[platform] = process
                self._login_read_tasks[platform] = asyncio.create_task(
                    self._read_login_output(platform, process)
                )

                entry = self._create_log_entry(
                    f"{platform} login check started. If the account is already logged in, it will be marked ready automatically.",
                    "success",
                )
                await self._push_log(entry)
                return True
            except Exception as e:
                self.login_states[platform] = {
                    "status": "error",
                    "started_at": now,
                    "finished_at": datetime.now(),
                    "error_message": str(e),
                }
                entry = self._create_log_entry(f"Failed to start {platform} login setup: {str(e)}", "error")
                await self._push_log(entry)
                return False

    def get_login_status(self, platform: str) -> dict:
        """Get login-only task status for a platform"""
        process = self.login_processes.get(platform)
        state = self.login_states.get(platform, {})

        if process and process.poll() is None:
            status = "running"
        else:
            status = state.get("status", "idle")

        return {
            "status": status,
            "platform": platform,
            "started_at": state.get("started_at").isoformat() if state.get("started_at") else None,
            "finished_at": state.get("finished_at").isoformat() if state.get("finished_at") else None,
            "error_message": state.get("error_message"),
            "has_local_state": self._has_local_login_state(platform),
        }

    def get_status(self) -> dict:
        """Get current status"""
        return {
            "status": self.status,
            "platform": self.current_config.platform.value if self.current_config else None,
            "crawler_type": self.current_config.crawler_type.value if self.current_config else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "error_message": None
        }

    def _build_command(self, config: CrawlerStartRequest) -> list:
        """Build main.py command line arguments"""
        cmd = [sys.executable, "main.py"]

        cmd.extend(["--platform", config.platform.value])
        cmd.extend(["--lt", config.login_type.value])
        cmd.extend(["--type", config.crawler_type.value])
        cmd.extend(["--save_data_option", config.save_option.value])
        cmd.extend(["--enable_cdp_mode", "false"])

        # Pass different arguments based on crawler type
        if config.crawler_type.value == "search" and config.keywords:
            cmd.extend(["--keywords", config.keywords])
        elif config.crawler_type.value == "detail" and config.specified_ids:
            cmd.extend(["--specified_id", config.specified_ids])
        elif config.crawler_type.value == "creator" and config.creator_ids:
            cmd.extend(["--creator_id", config.creator_ids])

        if config.start_page != 1:
            cmd.extend(["--start", str(config.start_page)])

        cmd.extend(["--get_comment", "true" if config.enable_comments else "false"])
        cmd.extend(["--get_sub_comment", "true" if config.enable_sub_comments else "false"])
        if config.platform.value == "xhs":
            cmd.extend(["--crawler_max_sleep_sec", str(XHS_CRAWL_SLEEP_SECONDS)])

        if config.max_notes_count is not None:
            cmd.extend(["--crawler_max_notes_count", str(config.max_notes_count)])

        if config.max_comments_count is not None:
            cmd.extend(["--max_comments_count_singlenotes", str(config.max_comments_count)])

        if config.cookies:
            cmd.extend(["--cookies", config.cookies])

        cmd.extend(["--headless", "true" if config.headless else "false"])

        return cmd

    def _build_login_command(self, config: LoginStartRequest) -> list:
        """Build a login-only main.py command line"""
        cmd = [
            sys.executable,
            "main.py",
            "--platform",
            config.platform.value,
            "--lt",
            config.login_type.value,
            "--type",
            "search",
            "--keywords",
            "login_state_check",
            "--get_comment",
            "false",
            "--get_sub_comment",
            "false",
            "--crawler_max_notes_count",
            "1",
            "--save_data_option",
            "jsonl",
            "--headless",
            "true" if config.headless else "false",
            "--enable_cdp_mode",
            "false",
            "--login_only",
            "true",
        ]
        if config.cookies:
            cmd.extend(["--cookies", config.cookies])
        return cmd

    def _has_local_login_state(self, platform: str) -> bool:
        """Check whether a platform persistent browser profile exists locally"""
        user_data_dir = self._project_root / "browser_data" / f"{platform}_user_data_dir"
        if not user_data_dir.exists():
            return False
        try:
            return any(user_data_dir.iterdir())
        except OSError:
            return False

    async def _read_output(self):
        """Asynchronously read process output"""
        loop = asyncio.get_event_loop()

        try:
            while self.process and self.process.poll() is None:
                # Read a line in thread pool
                line = await loop.run_in_executor(
                    None, self.process.stdout.readline
                )
                if line:
                    line = line.strip()
                    if line:
                        level = self._parse_log_level(line)
                        entry = self._create_log_entry(line, level)
                        await self._push_log(entry)

            # Read remaining output
            if self.process and self.process.stdout:
                remaining = await loop.run_in_executor(
                    None, self.process.stdout.read
                )
                if remaining:
                    for line in remaining.strip().split('\n'):
                        if line.strip():
                            level = self._parse_log_level(line)
                            entry = self._create_log_entry(line.strip(), level)
                            await self._push_log(entry)

            # Process ended
            if self.status == "running":
                exit_code = self.process.returncode if self.process else -1
                self.last_exit_code = exit_code
                if exit_code == 0:
                    entry = self._create_log_entry("Crawler completed successfully", "success")
                    await self._push_log(entry)
                    enrich_entry = await self._enrich_comments_with_content_titles()
                    if enrich_entry:
                        await self._push_log(enrich_entry)
                    risk_entry = await self._export_risk_comments()
                    if risk_entry:
                        await self._push_log(risk_entry)
                    report_entry = await self._build_and_notify_comment_report()
                    if report_entry:
                        await self._push_log(report_entry)
                else:
                    entry = self._create_log_entry(f"Crawler exited with code: {exit_code}", "warning")
                    await self._push_log(entry)
                self.status = "idle"
                self.current_config = None

        except asyncio.CancelledError:
            pass
        except Exception as e:
            entry = self._create_log_entry(f"Error reading output: {str(e)}", "error")
            await self._push_log(entry)

    async def _read_login_output(self, platform: str, process: subprocess.Popen):
        """Read login-only process output"""
        loop = asyncio.get_event_loop()

        try:
            while process.poll() is None:
                line = await loop.run_in_executor(None, process.stdout.readline)
                if line:
                    line = line.strip()
                    if line:
                        level = self._parse_log_level(line)
                        entry = self._create_log_entry(f"[login:{platform}] {line}", level)
                        await self._push_log(entry)

            if process.stdout:
                remaining = await loop.run_in_executor(None, process.stdout.read)
                if remaining:
                    for line in remaining.strip().split("\n"):
                        if line.strip():
                            level = self._parse_log_level(line)
                            entry = self._create_log_entry(f"[login:{platform}] {line.strip()}", level)
                            await self._push_log(entry)

            exit_code = process.returncode
            finished_at = datetime.now()
            if exit_code == 0:
                status = "success"
                message = f"{platform} login setup completed"
                level = "success"
                error_message = None
            else:
                status = "error"
                message = f"{platform} login setup exited with code: {exit_code}"
                level = "warning"
                error_message = message

            self.login_states[platform] = {
                **self.login_states.get(platform, {}),
                "status": status,
                "finished_at": finished_at,
                "error_message": error_message,
            }
            entry = self._create_log_entry(message, level)
            await self._push_log(entry)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.login_states[platform] = {
                **self.login_states.get(platform, {}),
                "status": "error",
                "finished_at": datetime.now(),
                "error_message": str(e),
            }
            entry = self._create_log_entry(f"Error reading {platform} login output: {str(e)}", "error")
            await self._push_log(entry)
        finally:
            current = self.login_processes.get(platform)
            if current is process:
                self.login_processes.pop(platform, None)
            self._login_read_tasks.pop(platform, None)

    async def _export_risk_comments(self) -> Optional[LogEntry]:
        """Append comments that hit configured risk words to a daily CSV file."""
        config = self.current_config
        if not config or not config.risk_words.strip():
            return None

        risk_words = [word.strip() for word in config.risk_words.split(",") if word.strip()]
        if not risk_words:
            return None

        platform = config.platform.value
        data_platform = PLATFORM_DATA_DIRS.get(platform, platform)
        crawler_type = config.crawler_type.value
        comments_file = self._project_root / "data" / data_platform / "csv" / f"{crawler_type}_comments_{datetime.now().strftime('%Y-%m-%d')}.csv"
        if not comments_file.exists():
            return self._create_log_entry(f"No comments CSV found for risk scan: {comments_file}", "warning")

        risk_dir = self._project_root / "data" / data_platform / "risk"
        risk_dir.mkdir(parents=True, exist_ok=True)
        risk_file = risk_dir / f"risk_comments_{datetime.now().strftime('%Y-%m-%d')}.csv"
        content_titles = self._load_content_titles_for_risk(platform, crawler_type)

        fieldnames = [
            "content_title",
            "detected_at",
            "platform",
            "monitor_account",
            "content_id",
            "comment_id",
            "username",
            "risk_word",
            "comment_content",
            "source_comments_file",
        ]
        existing_keys = set()
        if risk_file.exists():
            with risk_file.open("r", newline="", encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    existing_keys.add((row.get("platform"), row.get("comment_id"), row.get("risk_word")))

        new_rows = []
        with comments_file.open("r", newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                content = row.get("content") or row.get("comment_text") or row.get("text") or ""
                if not content:
                    continue
                comment_id = row.get("comment_id") or row.get("id") or ""
                content_id = (
                    row.get("note_id")
                    or row.get("aweme_id")
                    or row.get("video_id")
                    or row.get("bvid")
                    or row.get("content_id")
                    or ""
                )
                username = (
                    row.get("nickname")
                    or row.get("user_nickname")
                    or row.get("user_name")
                    or row.get("uname")
                    or row.get("name")
                    or ""
                )
                for word in risk_words:
                    if word not in content:
                        continue
                    key = (platform, comment_id, word)
                    if key in existing_keys:
                        continue
                    existing_keys.add(key)
                    new_rows.append({
                        "content_title": content_titles.get(content_id, ""),
                        "detected_at": datetime.now().isoformat(timespec="seconds"),
                        "platform": platform,
                        "monitor_account": config.creator_ids,
                        "content_id": content_id,
                        "comment_id": comment_id,
                        "username": username,
                        "risk_word": word,
                        "comment_content": content,
                        "source_comments_file": str(comments_file),
                    })

        if not new_rows:
            return self._create_log_entry("Risk scan completed: no new risky comments matched", "info")

        file_exists = risk_file.exists()
        with risk_file.open("a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists or risk_file.stat().st_size == 0:
                writer.writeheader()
            writer.writerows(new_rows)

        return self._create_log_entry(
            f"Risk scan completed: appended {len(new_rows)} rows to {risk_file}",
            "success",
        )

    async def _enrich_comments_with_content_titles(self) -> Optional[LogEntry]:
        """Rewrite the current comments CSV with the content title as the first column."""
        config = self.current_config
        if not config:
            return None

        platform = config.platform.value
        data_platform = PLATFORM_DATA_DIRS.get(platform, platform)
        crawler_type = config.crawler_type.value
        date_key = datetime.now().strftime("%Y-%m-%d")
        comments_file = self._project_root / "data" / data_platform / "csv" / f"{crawler_type}_comments_{date_key}.csv"
        if not comments_file.exists():
            return None

        content_titles = self._load_content_titles_for_risk(platform, crawler_type)
        if not content_titles:
            return self._create_log_entry("Comment table enrichment skipped: no content title CSV found", "warning")

        with comments_file.open("r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            old_fieldnames = reader.fieldnames or []

        if not rows or not old_fieldnames:
            return None

        fieldnames = ["作品名"] + [field for field in old_fieldnames if field not in {"作品名", "content_title"}]
        enriched_count = 0
        with comments_file.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                content_id = (
                    row.get("note_id")
                    or row.get("aweme_id")
                    or row.get("video_id")
                    or row.get("bvid")
                    or row.get("content_id")
                    or ""
                )
                title = row.get("作品名") or row.get("content_title") or content_titles.get(content_id, "")
                if title:
                    enriched_count += 1
                row["作品名"] = title
                writer.writerow({field: row.get(field, "") for field in fieldnames})

        return self._create_log_entry(
            f"Comment table enriched with content titles: {enriched_count}/{len(rows)} rows",
            "success",
        )

    def _load_content_titles_for_risk(self, platform: str, crawler_type: str) -> Dict[str, str]:
        date_key = datetime.now().strftime("%Y-%m-%d")
        data_platform = PLATFORM_DATA_DIRS.get(platform, platform)
        csv_dir = self._project_root / "data" / data_platform / "csv"
        titles: Dict[str, str] = {}
        for item_type in ("contents", "notes", "videos"):
            contents_file = csv_dir / f"{crawler_type}_{item_type}_{date_key}.csv"
            if not contents_file.exists():
                continue
            with contents_file.open("r", newline="", encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    content_id = (
                        row.get("note_id")
                        or row.get("aweme_id")
                        or row.get("video_id")
                        or row.get("bvid")
                        or row.get("content_id")
                        or row.get("id")
                        or ""
                    )
                    title = row.get("title") or row.get("desc") or row.get("content") or ""
                    if content_id and title:
                        titles[content_id] = title
        return titles

    async def _build_and_notify_comment_report(self) -> Optional[LogEntry]:
        config = self.current_config
        if not config:
            return None

        result = comment_report_service.build_daily_report(
            risk_words=config.risk_words,
            monitor_accounts={config.platform.value: config.creator_ids},
        )
        sync_result = await feishu_sheet_sync_service.sync_report_file(result.report_file)
        if sync_result.skipped:
            sync_message = f"Feishu sheet sync skipped: {sync_result.message}"
        elif sync_result.success:
            sync_message = f"Feishu sheet synced: sheet_id={sync_result.sheet_id}"
        else:
            sync_message = f"Feishu sheet sync failed: {sync_result.message}"

        notify_count = 0
        if config.notify and result.notify_rows:
            notify_count = await self._send_feishu_report_digest(result.notify_rows)

        return self._create_log_entry(
            f"Daily comment report refreshed: {result.report_file}, rows={len(result.rows)}, Feishu digest rows={notify_count}. {sync_message}",
            "success",
        )

    def _load_feishu_bot_config(self) -> Optional[Dict[str, str]]:
        """Load Feishu bot webhook and secret from the local markdown file."""
        config_path = self._project_root / "config" / "feishu_bot.local.md"
        if not config_path.exists():
            return None

        content = config_path.read_text(encoding="utf-8")
        webhook_match = re.search(r"Webhook:\s*`([^`]+)`", content)
        secret_match = re.search(r"Secret:\s*`([^`]+)`", content)
        if not webhook_match:
            return None

        return {
            "webhook": webhook_match.group(1).strip(),
            "secret": secret_match.group(1).strip() if secret_match else "",
        }

    def _build_feishu_sign(self, timestamp: str, secret: str) -> str:
        string_to_sign = f"{timestamp}\n{secret}".encode("utf-8")
        digest = hmac.new(string_to_sign, b"", digestmod=hashlib.sha256).digest()
        return base64.b64encode(digest).decode("utf-8")

    async def _send_feishu_risk_notifications(self, rows: List[Dict[str, str]]) -> int:
        bot_config = self._load_feishu_bot_config()
        if not bot_config:
            entry = self._create_log_entry("Feishu bot config not found, skipped risk notifications", "warning")
            await self._push_log(entry)
            return 0

        webhook = bot_config["webhook"]
        secret = bot_config.get("secret", "")
        sent_count = 0
        async with httpx.AsyncClient(timeout=10) as client:
            for row in rows:
                timestamp = str(int(time.time()))
                text = (
                    "评论风险命中\n"
                    f"平台：{row.get('platform', '')}\n"
                    f"监控账号：{row.get('monitor_account', '')}\n"
                    f"风险词：{row.get('risk_word', '')}\n"
                    f"评论用户：{row.get('username', '')}\n"
                    f"评论内容：{row.get('comment_content', '')}\n"
                    f"内容ID：{row.get('content_id', '')}\n"
                    f"评论ID：{row.get('comment_id', '')}\n"
                    f"检测时间：{row.get('detected_at', '')}"
                )
                payload: Dict[str, Any] = {
                    "timestamp": timestamp,
                    "msg_type": "text",
                    "content": {"text": text},
                }
                if secret:
                    payload["sign"] = self._build_feishu_sign(timestamp, secret)

                try:
                    response = await client.post(webhook, json=payload)
                    response.raise_for_status()
                    result = response.json()
                    if result.get("code", 0) == 0:
                        sent_count += 1
                    else:
                        entry = self._create_log_entry(f"Feishu notification failed: {result}", "warning")
                        await self._push_log(entry)
                except Exception as e:
                    entry = self._create_log_entry(f"Feishu notification error: {str(e)}", "error")
                    await self._push_log(entry)

        return sent_count

    async def _send_feishu_report_digest(self, rows: List[Dict[str, str]]) -> int:
        broadcast_settings = broadcast_settings_service.get_settings()
        if not broadcast_settings.enabled:
            entry = self._create_log_entry("Feishu broadcast disabled, skipped report digest", "info")
            await self._push_log(entry)
            return 0

        bot_config = self._load_feishu_bot_config()
        if not bot_config:
            entry = self._create_log_entry("Feishu bot config not found, skipped report digest", "warning")
            await self._push_log(entry)
            return 0

        top_rows = rows[:8]
        red_count = sum(1 for row in rows if row.get("高亮等级") == "红色")
        orange_count = sum(1 for row in rows if row.get("高亮等级") == "橙色")
        file_labels = broadcast_settings_service.selected_file_labels(broadcast_settings.selected_files)
        lines = [
            f"评论监控摘要｜{broadcast_settings.feishu_group_name}｜{datetime.now().strftime('%H:%M')}",
            f"新增高亮：{len(rows)} 条｜红色 {red_count}｜橙色 {orange_count}",
        ]
        if file_labels:
            lines.append(f"相关文件：{'、'.join(file_labels)}")
        for index, row in enumerate(top_rows, start=1):
            content = row.get("评论内容", "")
            if len(content) > 42:
                content = content[:42] + "..."
            risk_word = row.get("风险词") or "非风险高赞"
            lines.append(
                f"{index}. {row.get('平台')}｜{risk_word}｜赞 {row.get('点赞总数')} (+{row.get('点赞新增')})｜{row.get('评论用户')}\n"
                f"“{content}”"
            )
        if len(rows) > len(top_rows):
            lines.append(f"另有 {len(rows) - len(top_rows)} 条，请看每日汇总表。")

        webhook = bot_config["webhook"]
        secret = bot_config.get("secret", "")
        timestamp = str(int(time.time()))
        payload: Dict[str, Any] = {
            "timestamp": timestamp,
            "msg_type": "text",
            "content": {"text": "\n".join(lines)},
        }
        if secret:
            payload["sign"] = self._build_feishu_sign(timestamp, secret)

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(webhook, json=payload)
                response.raise_for_status()
                result = response.json()
                if result.get("code", 0) == 0:
                    return len(rows)
                entry = self._create_log_entry(f"Feishu report digest failed: {result}", "warning")
                await self._push_log(entry)
        except Exception as e:
            entry = self._create_log_entry(f"Feishu report digest error: {str(e)}", "error")
            await self._push_log(entry)
        return 0


# Global singleton
crawler_manager = CrawlerManager()
