# CommentGuard Killer（恶评 Killer）

面向品牌/内容团队的多平台评论区风险监控工具。项目基于开源爬虫能力做了产品化封装，重点用于自有账号、已授权账号和公司内容资产的评论巡检。

## 功能

- 支持小红书、抖音、Bilibili 评论区扫描。
- 支持监控账号、全作品/指定数量、全评论/指定数量、二级评论开关。
- 支持风险词命中记录，输出评论用户、完整评论内容、风险词、作品名、内容 ID、评论 ID 和检测时间。
- 支持非风险但高赞/点赞增长明显的评论汇总。
- 默认生成 CSV 文件，文件中心可查看、筛选和打开本地位置。
- 支持飞书群机器人摘要播报。
- 预留飞书多维表格 Webhook/表格同步配置示例。
- 支持一次性扫描和定时监控任务。

## 合规使用

请仅监控公司自有账号、已授权账号或依法可处理的数据。请合理控制采集频率，不要进行大规模抓取、绕过访问控制、侵犯用户隐私或违反目标平台规则。

本仓库保留上游开源项目的许可证文件。后续二次分发、内部部署和商业化使用前，请先确认许可证和平台条款。

## 本地配置

本项目会读取本地配置文件，但不会把真实密钥提交到仓库。

- 飞书群机器人：复制 `config/feishu_bot.example.md` 为 `config/feishu_bot.local.md`。
- 飞书表格/知识库：复制 `config/feishu_docs.example.md` 为 `config/feishu_docs.local.md`。
- 飞书多维表格 Webhook：复制 `config/feishu_bitable_webhook.example.md` 为 `config/feishu_bitable_webhook.local.md`。
- 定时任务：运行时写入 `config/monitor_jobs.local.json`。
- 播报设置：运行时写入 `config/broadcast_settings.local.json`。

以上 `*.local.*` 文件已加入 `.gitignore`，不要提交真实 webhook、secret、cookie、浏览器缓存或采集结果。

## 启动

安装 Python 和 Node.js 依赖后：

```shell
uv sync
uv run playwright install chromium
cd webui
pnpm install
pnpm run build
cd ..
uv run uvicorn api.main:app --port 8080 --reload
```

访问：

```text
http://localhost:8080
```

开发前端时可单独启动：

```shell
cd webui
pnpm run dev
```

## 数据目录

- 原始采集数据：`data/`
- 每日汇总报表：`data/reports/`
- 浏览器登录态：`browser_data/`

这些目录默认不提交到 Git。
