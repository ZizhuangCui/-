# -*- coding: utf-8 -*-
import csv
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple


DEFAULT_RISK_WORDS = "版权,侵权,盗版,抄袭,搬运,未经授权,投诉,举报,律师函,起诉,下架"
REPORT_PLATFORMS = ("xhs", "dy", "bili")
PLATFORM_DATA_DIRS = {
    "xhs": "xhs",
    "dy": "douyin",
    "bili": "bili",
}
REPORT_HEADERS = [
    "作品名",
    "日期",
    "平台",
    "监控账号",
    "内容ID",
    "评论ID",
    "评论用户",
    "评论时间",
    "评论内容",
    "风险词",
    "是否风险词",
    "是否今日新增",
    "点赞总数",
    "昨日点赞数",
    "点赞新增",
    "高亮类型",
    "高亮等级",
    "来源评论CSV",
    "检测时间",
]


@dataclass
class ReportBuildResult:
    report_file: Path
    rows: List[Dict[str, str]]
    notify_rows: List[Dict[str, str]]


class CommentReportService:
    """Build daily comment summaries for Feishu Sheet syncing and compact bot digests."""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.report_dir = self.project_root / "data" / "reports"
        self.notify_state_dir = self.report_dir / "notify_state"

    def build_daily_report(
        self,
        risk_words: str = "",
        monitor_accounts: Optional[Dict[str, str]] = None,
        high_like_threshold: int = 100,
        like_growth_threshold: int = 20,
        date: Optional[datetime] = None,
    ) -> ReportBuildResult:
        target_date = date or datetime.now()
        date_key = target_date.strftime("%Y-%m-%d")
        previous_date = target_date - timedelta(days=1)
        risk_word_list = self._risk_words(risk_words)
        monitor_accounts = monitor_accounts or self._load_monitor_accounts()

        today_comments = self._load_comments_for_date(target_date)
        previous_comments = self._load_comments_for_date(previous_date)
        previous_by_key = {
            self._comment_key(item): item
            for item in previous_comments
            if self._comment_key(item)
        }

        rows: List[Dict[str, str]] = []
        for item in today_comments:
            key = self._comment_key(item)
            if not key:
                continue

            previous = previous_by_key.get(key)
            like_count = self._to_int(item.get("like_count"))
            previous_like = self._to_int(previous.get("like_count")) if previous else 0
            like_delta = max(like_count - previous_like, 0)
            content = item.get("content", "")
            matched_words = [word for word in risk_word_list if word and word in content]
            is_risk = bool(matched_words)
            is_new = previous is None
            is_high_like = like_count >= high_like_threshold
            is_growth = like_delta >= like_growth_threshold

            if not (is_risk or is_high_like or is_growth):
                continue

            highlight_type = self._highlight_type(is_risk, is_new, is_high_like, is_growth)
            highlight_level = self._highlight_level(is_risk, is_new, like_count, like_delta)
            row = {
                "作品名": item.get("content_title", ""),
                "日期": date_key,
                "平台": item.get("platform", ""),
                "监控账号": monitor_accounts.get(item.get("platform", ""), ""),
                "内容ID": item.get("content_id", ""),
                "评论ID": item.get("comment_id", ""),
                "评论用户": item.get("nickname", ""),
                "评论时间": self._format_comment_time(item.get("create_time")),
                "评论内容": content,
                "风险词": ",".join(matched_words),
                "是否风险词": "是" if is_risk else "否",
                "是否今日新增": "是" if is_new else "否",
                "点赞总数": str(like_count),
                "昨日点赞数": str(previous_like),
                "点赞新增": str(like_delta),
                "高亮类型": highlight_type,
                "高亮等级": highlight_level,
                "来源评论CSV": item.get("source_file", ""),
                "检测时间": datetime.now().isoformat(timespec="seconds"),
            }
            rows.append(row)

        rows.sort(
            key=lambda row: (
                self._highlight_rank(row["高亮等级"]),
                self._to_int(row["点赞新增"]),
                self._to_int(row["点赞总数"]),
            ),
            reverse=True,
        )

        report_file = self._write_report(date_key, rows)
        notify_rows = self._filter_new_notify_rows(date_key, rows)
        return ReportBuildResult(report_file=report_file, rows=rows, notify_rows=notify_rows)

    def _load_comments_for_date(self, date: datetime) -> List[Dict[str, str]]:
        date_key = date.strftime("%Y-%m-%d")
        latest_by_key: Dict[Tuple[str, str], Dict[str, str]] = {}
        for platform in REPORT_PLATFORMS:
            csv_dir = self.project_root / "data" / PLATFORM_DATA_DIRS.get(platform, platform) / "csv"
            content_titles = self._load_content_titles(platform, date_key)
            for file_path in sorted(csv_dir.glob(f"*_comments_{date_key}.csv")):
                with file_path.open("r", newline="", encoding="utf-8-sig") as f:
                    for row in csv.DictReader(f):
                        item = self._normalize_comment(platform, row, file_path, content_titles)
                        key = self._comment_key(item)
                        if not key:
                            continue
                        latest_by_key[key] = item
        return list(latest_by_key.values())

    def _load_content_titles(self, platform: str, date_key: str) -> Dict[str, str]:
        csv_dir = self.project_root / "data" / PLATFORM_DATA_DIRS.get(platform, platform) / "csv"
        titles: Dict[str, str] = {}
        for pattern in (f"*_contents_{date_key}.csv", f"*_notes_{date_key}.csv", f"*_videos_{date_key}.csv"):
            for file_path in sorted(csv_dir.glob(pattern)):
                with file_path.open("r", newline="", encoding="utf-8-sig") as f:
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

    def _normalize_comment(self, platform: str, row: Dict[str, str], file_path: Path, content_titles: Dict[str, str]) -> Dict[str, str]:
        content_id = (
            row.get("note_id")
            or row.get("aweme_id")
            or row.get("video_id")
            or row.get("bvid")
            or row.get("content_id")
            or ""
        )
        return {
            "platform": platform,
            "content_id": content_id,
            "content_title": row.get("作品名") or row.get("content_title") or content_titles.get(content_id, ""),
            "comment_id": row.get("comment_id") or row.get("id") or "",
            "nickname": row.get("nickname") or row.get("user_nickname") or row.get("uname") or row.get("user_name") or "",
            "create_time": row.get("create_time") or row.get("ctime") or "",
            "content": row.get("content") or row.get("comment_text") or row.get("text") or "",
            "like_count": row.get("like_count") or row.get("liked_count") or row.get("digg_count") or "0",
            "source_file": str(file_path),
        }

    def _load_monitor_accounts(self) -> Dict[str, str]:
        store_path = self.project_root / "config" / "monitor_jobs.local.json"
        if not store_path.exists():
            return {}
        try:
            payload = json.loads(store_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

        accounts = {}
        for job in payload.get("jobs", []):
            config = job.get("config") or {}
            platform = job.get("platform") or config.get("platform")
            creator_ids = config.get("creator_ids")
            if platform and creator_ids:
                accounts[platform] = creator_ids
        return accounts

    def _risk_words(self, risk_words: str) -> List[str]:
        raw = risk_words or self._load_risk_words_from_monitor_jobs() or DEFAULT_RISK_WORDS
        return [word.strip() for word in raw.split(",") if word.strip()]

    def _load_risk_words_from_monitor_jobs(self) -> str:
        store_path = self.project_root / "config" / "monitor_jobs.local.json"
        if not store_path.exists():
            return ""
        try:
            payload = json.loads(store_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ""

        words = []
        for job in payload.get("jobs", []):
            config = job.get("config") or {}
            words.extend([word.strip() for word in str(config.get("risk_words") or "").split(",") if word.strip()])
        return ",".join(dict.fromkeys(words))

    def _filter_new_notify_rows(self, date_key: str, rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
        self.notify_state_dir.mkdir(parents=True, exist_ok=True)
        state_file = self.notify_state_dir / f"notified_{date_key}.csv"
        existing = set()
        if state_file.exists():
            with state_file.open("r", newline="", encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    existing.add((row.get("平台"), row.get("评论ID"), row.get("高亮类型")))

        notify_rows = []
        for row in rows:
            if row["高亮等级"] == "普通":
                continue
            key = (row["平台"], row["评论ID"], row["高亮类型"])
            if key in existing:
                continue
            existing.add(key)
            notify_rows.append(row)

        if notify_rows:
            file_exists = state_file.exists()
            with state_file.open("a", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=["平台", "评论ID", "高亮类型", "通知时间"])
                if not file_exists or state_file.stat().st_size == 0:
                    writer.writeheader()
                for row in notify_rows:
                    writer.writerow({
                        "平台": row["平台"],
                        "评论ID": row["评论ID"],
                        "高亮类型": row["高亮类型"],
                        "通知时间": datetime.now().isoformat(timespec="seconds"),
                    })
        return notify_rows

    def _write_report(self, date_key: str, rows: List[Dict[str, str]]) -> Path:
        self.report_dir.mkdir(parents=True, exist_ok=True)
        report_file = self.report_dir / f"comment_daily_summary_{date_key}.csv"
        with report_file.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=REPORT_HEADERS)
            writer.writeheader()
            writer.writerows(rows)
        return report_file

    def _highlight_type(self, is_risk: bool, is_new: bool, is_high_like: bool, is_growth: bool) -> str:
        values = []
        if is_risk and is_new:
            values.append("新增敏感")
        elif is_risk:
            values.append("敏感词")
        if is_high_like:
            values.append("高赞")
        if is_growth:
            values.append("点赞增长")
        return ",".join(values) or "普通"

    def _highlight_level(self, is_risk: bool, is_new: bool, like_count: int, like_delta: int) -> str:
        if (is_risk and is_new) or like_delta >= 100:
            return "红色"
        if is_risk or like_delta >= 20 or like_count >= 100:
            return "橙色"
        return "普通"

    def _highlight_rank(self, level: str) -> int:
        return {"红色": 3, "橙色": 2, "黄色": 1}.get(level, 0)

    def _comment_key(self, item: Dict[str, str]) -> Optional[Tuple[str, str]]:
        platform = item.get("platform")
        comment_id = item.get("comment_id")
        if not platform or not comment_id:
            return None
        return platform, comment_id

    def _to_int(self, value) -> int:
        try:
            return int(float(str(value or "0").strip()))
        except ValueError:
            return 0

    def _format_comment_time(self, value) -> str:
        timestamp = self._to_int(value)
        if not timestamp:
            return str(value or "")
        if timestamp > 10_000_000_000:
            timestamp = timestamp // 1000
        try:
            return datetime.fromtimestamp(timestamp).isoformat(timespec="seconds")
        except (OSError, ValueError):
            return str(value or "")


comment_report_service = CommentReportService()
