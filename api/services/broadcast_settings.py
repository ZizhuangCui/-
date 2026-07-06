# -*- coding: utf-8 -*-
import json
from pathlib import Path
from typing import Dict, List

from ..schemas.settings import BroadcastSettings


FILE_LABELS: Dict[str, str] = {
    "daily_summary": "每日评论汇总",
    "risk_comments": "风险评论",
    "raw_comments": "原始评论全量",
}


class BroadcastSettingsService:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.config_path = self.project_root / "config" / "broadcast_settings.local.json"

    def get_settings(self) -> BroadcastSettings:
        if not self.config_path.exists():
            return BroadcastSettings()
        try:
            payload = json.loads(self.config_path.read_text(encoding="utf-8"))
            return BroadcastSettings.model_validate(payload)
        except Exception:
            return BroadcastSettings()

    def save_settings(self, settings: BroadcastSettings) -> BroadcastSettings:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps(settings.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return settings

    def preview_text(self, settings: BroadcastSettings | None = None) -> str:
        settings = settings or self.get_settings()
        files = self.selected_file_labels(settings.selected_files)
        period = "按爬取周期播报" if settings.period_mode == "crawl_cycle" else f"每 {settings.custom_interval_minutes} 分钟播报"
        return (
            f"评论监控摘要｜{settings.feishu_group_name}\n"
            f"播报周期：{period}\n"
            f"播报文件：{'、'.join(files) if files else '未选择'}\n\n"
            "新增高亮：3 条｜红色 1｜橙色 2\n"
            "1. 小红书｜宋威龙｜赞 50 (+50)｜一***🌺\n"
            "“宋威龙吗[哭惹R]”\n"
            "2. 小红书｜非风险高赞｜赞 352 (+12)｜W***覺\n"
            "“感觉需要跟乙游联动一下改进建模审美...”\n\n"
            "详情请查看：每日评论汇总 / 风险评论"
        )

    def selected_file_labels(self, selected_files: List[str]) -> List[str]:
        return [FILE_LABELS[item] for item in selected_files if item in FILE_LABELS]


broadcast_settings_service = BroadcastSettingsService()
