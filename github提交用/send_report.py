#!/usr/bin/env python3
"""
生成飞书消息并发送，附带Excel文件
"""

import json
from datetime import datetime
from pathlib import Path
import pandas as pd

# 飞书配置
APP_ID = "cli_a94d6954a4b8dbd7"
APP_SECRET = "wOacuw2bYhyhwRlsvzGx4dDMipKxA3pX"
MY_USER_ID = "ou_b51a06093db685bb366ecc1742aa6705"

import requests


def get_app_access_token(app_id, app_secret):
    """获取飞书应用访问令牌"""
    url = "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal"
    headers = {"Content-Type": "application/json; charset=utf-8"}
    data = {"app_id": app_id, "app_secret": app_secret}
    
    response = requests.post(url, headers=headers, json=data)
    result = response.json()
    
    if result.get("code") == 0:
        return result.get("app_access_token")
    else:
        print(f"获取token失败: {result}")
        return None


def send_message_to_user(app_token, user_id, message):
    """给用户发送消息"""
    url = "https://open.feishu.cn/open-apis/im/v1/messages"
    headers = {
        "Authorization": f"Bearer {app_token}",
        "Content-Type": "application/json"
    }
    
    params = {"receive_id_type": "open_id"}
    data = {
        "receive_id": user_id,
        "msg_type": "text",
        "content": json.dumps({"text": message})
    }
    
    response = requests.post(url, headers=headers, params=params, json=data)
    result = response.json()
    
    if result.get("code") == 0:
        print(f"✓ 消息发送成功!")
        return True
    else:
        print(f"✗ 消息发送失败: {result}")
        return False


def upload_file_to_feishu(app_token, file_path):
    """上传文件到飞书"""
    url = "https://open.feishu.cn/open-apis/im/v1/files"
    headers = {
        "Authorization": f"Bearer {app_token}"
    }
    
    with open(file_path, "rb") as f:
        files = {"file": f}
        data = {"file_type": "xlsx", "file_name": Path(file_path).name}
        response = requests.post(url, headers=headers, files=files, data=data)
    
    result = response.json()
    if result.get("code") == 0:
        return result.get("data", {}).get("file_key")
    else:
        print(f"文件上传失败: {result}")
        return None


def send_file_to_user(app_token, user_id, file_key):
    """发送文件给用户"""
    url = "https://open.feishu.cn/open-apis/im/v1/messages"
    headers = {
        "Authorization": f"Bearer {app_token}",
        "Content-Type": "application/json"
    }
    
    params = {"receive_id_type": "open_id"}
    data = {
        "receive_id": user_id,
        "msg_type": "file",
        "content": json.dumps({"file_key": file_key})
    }
    
    response = requests.post(url, headers=headers, params=params, json=data)
    result = response.json()
    
    if result.get("code") == 0:
        print(f"✓ 文件发送成功!")
        return True
    else:
        print(f"✗ 文件发送失败: {result}")
        return False


def generate_report():
    """生成招标报告"""
    # 读取数据
    date_str = "2026-03-28"
    file_path = Path.home() / "Desktop" / "上海招标文件" / f"上海采购公告_全部_{date_str}.xlsx"
    
    if not file_path.exists():
        return None, None, "未找到数据文件"
    
    df = pd.read_excel(file_path)
    
    # 筛选关键词
    keywords = ["弱电", "信息化", "智慧校园", "智能化", "安防", "监控", "网络", "机房", "数据中心", "多媒体", "教室", "校园", "教育信息化"]
    
    matched = []
    for _, row in df.iterrows():
        title = str(row.get("项目名称", ""))
        for kw in keywords:
            if kw in title:
                matched.append({
                    "name": title,
                    "keyword": kw,
                    "url": row.get("具体信息", ""),
                    "date": row.get("公告日期", "")
                })
                break
    
    # 生成消息
    report = f"📋 上海政府采购网招标公告 ({date_str})\n"
    report += f"━━━━━━━━━━━━━━━━━━━━\n"
    report += f"📊 当日公告总数: {len(df)} 条\n"
    report += f"✅ 匹配项目: {len(matched)} 条\n\n"
    
    if matched:
        report += "🎯 匹配项目详情:\n"
        for i, item in enumerate(matched, 1):
            report += f"\n{i}. [{item['keyword']}] {item['name']}\n"
            report += f"   📅 日期: {item['date']}\n"
            report += f"   🔗 链接: {item['url']}\n"
    else:
        report += "📝 当日无匹配项目\n\n"
        report += "📌 全部公告:\n"
        for i, row in df.iterrows():
            report += f"{i+1}. {row['项目名称']}\n"
    
    report += f"\n━━━━━━━━━━━━━━━━━━━━\n"
    report += f"📁 Excel文件位置: 桌面/上海招标文件/\n"
    report += f"⏰ 发送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    return report, str(file_path), len(matched)


def main():
    print("=" * 60)
    print("生成招标报告并发送飞书")
    print("=" * 60)
    
    # 生成报告
    print("\n正在生成报告...")
    report, file_path, matched_count = generate_report()
    
    if report is None:
        print("生成报告失败")
        return
    
    print(f"\n报告预览:\n{'='*60}")
    print(report[:500] + "..." if len(report) > 500 else report)
    print('='*60)
    
    # 发送飞书
    print("\n正在发送飞书消息...")
    token = get_app_access_token(APP_ID, APP_SECRET)
    if not token:
        print("获取token失败")
        return
    
    # 先发送文字消息
    success = send_message_to_user(token, MY_USER_ID, report)
    
    if success and file_path:
        print("\n正在上传Excel文件...")
        file_key = upload_file_to_feishu(token, file_path)
        if file_key:
            send_file_to_user(token, MY_USER_ID, file_key)
    
    if success:
        print(f"\n✓ 报告和Excel已发送至你的飞书")
    else:
        print(f"\n✗ 发送失败")


if __name__ == "__main__":
    main()
