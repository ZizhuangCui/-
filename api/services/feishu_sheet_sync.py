# -*- coding: utf-8 -*-
import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import httpx


@dataclass
class FeishuSheetSyncResult:
    success: bool
    skipped: bool
    message: str
    spreadsheet_token: str = ""
    sheet_id: str = ""


class FeishuSheetSyncService:
    """Sync daily comment reports to a Feishu/Lark spreadsheet."""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.config_path = self.project_root / "config" / "feishu_docs.local.md"
        self.base_url = "https://open.feishu.cn"

    async def sync_report_file(self, report_file: Path) -> FeishuSheetSyncResult:
        config = self._load_config()
        if not config:
            return FeishuSheetSyncResult(
                success=False,
                skipped=True,
                message="config/feishu_docs.local.md not found or incomplete",
            )

        spreadsheet_token = config["spreadsheet_token"]
        sheet_title = self._sheet_title_from_file(report_file)
        values = self._read_csv_values(report_file)
        if not values:
            return FeishuSheetSyncResult(
                success=False,
                skipped=True,
                message=f"report file has no values: {report_file}",
                spreadsheet_token=spreadsheet_token,
            )

        async with httpx.AsyncClient(timeout=20) as client:
            tenant_token = await self._get_tenant_access_token(client, config)
            sheet_id = await self._get_or_create_sheet(client, tenant_token, spreadsheet_token, sheet_title)
            await self._write_values(client, tenant_token, spreadsheet_token, sheet_id, values)

        return FeishuSheetSyncResult(
            success=True,
            skipped=False,
            message=f"synced {len(values) - 1} rows to Feishu sheet {sheet_title}",
            spreadsheet_token=spreadsheet_token,
            sheet_id=sheet_id,
        )

    def _load_config(self) -> Optional[Dict[str, str]]:
        if not self.config_path.exists():
            return None

        content = self.config_path.read_text(encoding="utf-8")
        fields = {
            "app_id": self._extract(content, "App ID"),
            "app_secret": self._extract(content, "App Secret"),
            "spreadsheet_token": self._extract(content, "Spreadsheet Token"),
        }
        if not all(fields.values()):
            return None
        return fields

    def _extract(self, content: str, label: str) -> str:
        match = re.search(rf"{re.escape(label)}:\s*`([^`]+)`", content)
        if not match:
            return ""
        value = match.group(1).strip()
        if value.startswith("your-") or value.startswith("optional_") or value in {"cli_xxx", "xxx", "shtcnxxx"}:
            return ""
        return value

    def _sheet_title_from_file(self, report_file: Path) -> str:
        match = re.search(r"(\d{4}-\d{2}-\d{2})", report_file.name)
        return match.group(1) if match else report_file.stem[:31]

    def _read_csv_values(self, report_file: Path) -> List[List[str]]:
        with report_file.open("r", newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            return [[str(cell) for cell in row] for row in reader]

    async def _get_tenant_access_token(self, client: httpx.AsyncClient, config: Dict[str, str]) -> str:
        response = await client.post(
            f"{self.base_url}/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": config["app_id"], "app_secret": config["app_secret"]},
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("tenant_access_token")
        if not token:
            raise RuntimeError(f"failed to get tenant_access_token: {payload}")
        return token

    async def _get_or_create_sheet(
        self,
        client: httpx.AsyncClient,
        tenant_token: str,
        spreadsheet_token: str,
        sheet_title: str,
    ) -> str:
        headers = {"Authorization": f"Bearer {tenant_token}"}
        response = await client.get(
            f"{self.base_url}/open-apis/sheets/v3/spreadsheets/{spreadsheet_token}/sheets/query",
            headers=headers,
        )
        response.raise_for_status()
        payload = response.json()
        for sheet in payload.get("data", {}).get("sheets", []):
            title = sheet.get("title") or sheet.get("properties", {}).get("title")
            sheet_id = sheet.get("sheet_id") or sheet.get("properties", {}).get("sheet_id")
            if title == sheet_title and sheet_id:
                return sheet_id

        response = await client.post(
            f"{self.base_url}/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/sheets_batch_update",
            headers=headers,
            json={
                "requests": [
                    {
                        "addSheet": {
                            "properties": {
                                "title": sheet_title,
                                "index": 0,
                            }
                        }
                    }
                ]
            },
        )
        response.raise_for_status()
        payload = response.json()
        replies = payload.get("data", {}).get("replies", [])
        for reply in replies:
            properties = reply.get("addSheet", {}).get("properties", {})
            sheet_id = properties.get("sheetId") or properties.get("sheet_id")
            if sheet_id:
                return sheet_id
        raise RuntimeError(f"failed to create sheet {sheet_title}: {payload}")

    async def _write_values(
        self,
        client: httpx.AsyncClient,
        tenant_token: str,
        spreadsheet_token: str,
        sheet_id: str,
        values: List[List[str]],
    ):
        headers = {"Authorization": f"Bearer {tenant_token}"}
        column_count = max(len(row) for row in values)
        row_count = len(values)
        range_name = f"{sheet_id}!A1:{self._column_name(column_count)}{row_count}"
        response = await client.put(
            f"{self.base_url}/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values",
            headers=headers,
            json={"valueRange": {"range": range_name, "values": values}},
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code", 0) != 0:
            raise RuntimeError(f"failed to write sheet values: {payload}")

    def _column_name(self, index: int) -> str:
        name = ""
        while index:
            index, remainder = divmod(index - 1, 26)
            name = chr(65 + remainder) + name
        return name or "A"


feishu_sheet_sync_service = FeishuSheetSyncService()
