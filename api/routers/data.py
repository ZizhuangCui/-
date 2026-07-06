# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/api/routers/data.py
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

import os
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/data", tags=["data"])

# Data directory
DATA_DIR = Path(__file__).parent.parent.parent / "data"


PLATFORM_LABELS = {
    "xhs": "小红书",
    "dy": "抖音",
    "douyin": "抖音",
    "bili": "Bilibili",
    "ks": "快手",
    "wb": "微博",
    "tieba": "贴吧",
    "zhihu": "知乎",
}

PLATFORM_ALIASES = {
    "dy": "douyin",
}


def get_file_display_info(file_path: Path) -> dict:
    """Return user-facing file name, category and explanation."""
    rel_parts = file_path.relative_to(DATA_DIR).parts
    file_name = file_path.name
    date_match = None
    import re
    match = re.search(r"(\d{4}-\d{2}-\d{2})", file_name)
    if match:
        date_match = match.group(1)
    date_text = date_match or "未知日期"

    if len(rel_parts) >= 2 and rel_parts[0] == "reports":
        return {
            "display_name": f"每日评论汇总_{date_text}{file_path.suffix}",
            "platform": "reports",
            "platform_label": "汇总",
            "category": "daily_summary",
            "category_label": "每日汇总",
            "description": "风险词评论、非风险高赞评论、点赞增长评论的统一汇总，用于飞书多维表格同步。",
        }

    platform = rel_parts[0] if rel_parts else ""
    platform_label = PLATFORM_LABELS.get(platform, platform or "未知平台")

    if "risk" in rel_parts:
        return {
            "display_name": f"{platform_label}_风险评论_{date_text}{file_path.suffix}",
            "platform": platform,
            "platform_label": platform_label,
            "category": "risk_comments",
            "category_label": "风险评论",
            "description": "只包含命中风险词的评论，便于版权/舆情风险复核。",
        }

    if "comments" in file_name:
        return {
            "display_name": f"{platform_label}_原始评论全量_{date_text}{file_path.suffix}",
            "platform": platform,
            "platform_label": platform_label,
            "category": "raw_comments",
            "category_label": "原始评论",
            "description": "本次采集到的全部评论原始数据，是风险评论和每日汇总的来源。",
        }

    if any(key in file_name for key in ["contents", "notes", "videos"]):
        return {
            "display_name": f"{platform_label}_原始作品全量_{date_text}{file_path.suffix}",
            "platform": platform,
            "platform_label": platform_label,
            "category": "raw_contents",
            "category_label": "原始作品",
            "description": "内部来源文件：作品名已经合并进评论汇总，通常不需要单独打开。",
        }

    return {
        "display_name": file_name,
        "platform": platform,
        "platform_label": platform_label,
        "category": "other",
        "category_label": "其他文件",
        "description": "系统生成的数据文件。",
    }


def get_file_info(file_path: Path) -> dict:
    """Get file information"""
    stat = file_path.stat()
    record_count = None

    # Try to get record count
    try:
        if file_path.suffix == ".json":
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    record_count = len(data)
        elif file_path.suffix == ".csv":
            with open(file_path, "r", encoding="utf-8") as f:
                record_count = sum(1 for _ in f) - 1  # Subtract header row
    except Exception:
        pass

    display_info = get_file_display_info(file_path)
    return {
        "name": file_path.name,
        **display_info,
        "path": str(file_path.relative_to(DATA_DIR)),
        "size": stat.st_size,
        "modified_at": stat.st_mtime,
        "record_count": record_count,
        "type": file_path.suffix[1:] if file_path.suffix else "unknown"
    }


@router.get("/files")
async def list_data_files(platform: Optional[str] = None, file_type: Optional[str] = None):
    """Get data file list"""
    if not DATA_DIR.exists():
        return {"files": []}

    files = []
    supported_extensions = {".json", ".csv", ".xlsx", ".xls"}

    for root, dirs, filenames in os.walk(DATA_DIR):
        root_path = Path(root)
        for filename in filenames:
            file_path = root_path / filename
            if file_path.suffix.lower() not in supported_extensions:
                continue
            if "notify_state" in file_path.parts:
                continue
            if any(key in filename for key in ["contents", "notes", "videos"]):
                continue

            # Platform filter
            if platform:
                platform_filter = PLATFORM_ALIASES.get(platform.lower(), platform.lower())
                rel_path = str(file_path.relative_to(DATA_DIR))
                if platform_filter not in rel_path.lower():
                    continue

            # Type filter
            if file_type and file_path.suffix[1:].lower() != file_type.lower():
                continue

            try:
                files.append(get_file_info(file_path))
            except Exception:
                continue

    # Sort by modification time (newest first)
    files.sort(key=lambda x: x["modified_at"], reverse=True)

    return {"files": files}


@router.get("/files/{file_path:path}")
async def get_file_content(file_path: str, preview: bool = True, limit: int = 100):
    """Get file content or preview"""
    full_path = DATA_DIR / file_path

    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    if not full_path.is_file():
        raise HTTPException(status_code=400, detail="Not a file")

    # Security check: ensure within DATA_DIR
    try:
        full_path.resolve().relative_to(DATA_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    if preview:
        # Return preview data
        try:
            if full_path.suffix == ".json":
                with open(full_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return {"data": data[:limit], "total": len(data)}
                    return {"data": data, "total": 1}
            elif full_path.suffix == ".csv":
                import csv
                with open(full_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    rows = []
                    for i, row in enumerate(reader):
                        if i >= limit:
                            break
                        rows.append(row)
                    # Re-read to get total count
                    f.seek(0)
                    total = sum(1 for _ in f) - 1
                    return {"data": rows, "total": total}
            elif full_path.suffix.lower() in (".xlsx", ".xls"):
                import pandas as pd
                # Read first limit rows
                df = pd.read_excel(full_path, nrows=limit)
                # Get total row count (only read first column to save memory)
                df_count = pd.read_excel(full_path, usecols=[0])
                total = len(df_count)
                # Convert to list of dictionaries, handle NaN values
                rows = df.where(pd.notnull(df), None).to_dict(orient='records')
                return {
                    "data": rows,
                    "total": total,
                    "columns": list(df.columns)
                }
            else:
                raise HTTPException(status_code=400, detail="Unsupported file type for preview")
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON file")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        # Return file download
        return FileResponse(
            path=full_path,
            filename=full_path.name,
            media_type="application/octet-stream"
        )


@router.get("/download/{file_path:path}")
async def download_file(file_path: str):
    """Download file"""
    full_path = DATA_DIR / file_path

    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    if not full_path.is_file():
        raise HTTPException(status_code=400, detail="Not a file")

    # Security check
    try:
        full_path.resolve().relative_to(DATA_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    return FileResponse(
        path=full_path,
        filename=full_path.name,
        media_type="application/octet-stream"
    )


@router.post("/reveal/{file_path:path}")
async def reveal_file(file_path: str):
    """Reveal a generated file in the local file manager."""
    full_path = DATA_DIR / file_path

    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    if not full_path.is_file():
        raise HTTPException(status_code=400, detail="Not a file")

    try:
        resolved_path = full_path.resolve()
        resolved_path.relative_to(DATA_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(resolved_path)])
        elif sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", str(resolved_path)])
        else:
            subprocess.Popen(["xdg-open", str(resolved_path.parent)])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reveal file: {e}")

    return {"status": "ok", "path": str(resolved_path)}


@router.get("/stats")
async def get_data_stats():
    """Get data statistics"""
    if not DATA_DIR.exists():
        return {"total_files": 0, "total_size": 0, "by_platform": {}, "by_type": {}}

    stats = {
        "total_files": 0,
        "total_size": 0,
        "by_platform": {},
        "by_type": {}
    }

    supported_extensions = {".json", ".csv", ".xlsx", ".xls"}

    for root, dirs, filenames in os.walk(DATA_DIR):
        root_path = Path(root)
        for filename in filenames:
            file_path = root_path / filename
            if file_path.suffix.lower() not in supported_extensions:
                continue

            try:
                stat = file_path.stat()
                stats["total_files"] += 1
                stats["total_size"] += stat.st_size

                # Statistics by type
                file_type = file_path.suffix[1:].lower()
                stats["by_type"][file_type] = stats["by_type"].get(file_type, 0) + 1

                # Statistics by platform (inferred from path)
                rel_path = str(file_path.relative_to(DATA_DIR))
                for platform in ["xhs", "dy", "ks", "bili", "wb", "tieba", "zhihu"]:
                    if platform in rel_path.lower():
                        stats["by_platform"][platform] = stats["by_platform"].get(platform, 0) + 1
                        break
            except Exception:
                continue

    return stats
