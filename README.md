# 上海政府采购数据自动采集系统

## 🚀 项目简介

本项目用于自动采集 **上海市政府采购网采购公告**，并生成结构化 Excel 报告，用于：

- 招标信息跟踪  
- 投标机会筛选  
- 项目数据分析  

系统特点：

- 接口抓取（稳定、高效）
- iframe解析（完整获取详情）
- 正则提取（处理非结构化文本）
- 支持关键词筛选（如弱电工程）
- 支持自定义时间区间
- 支持 OpenClaw + 飞书自动推送报告

---

## 📦 项目结构
├── grab_openapi_v3.py # v3：稳定获取采购公告列表
├── fetch_sh_zfcg_v15_format.py # v15：详情解析 + Excel格式输出
├── README.md


说明：
- v3 → 获取“采购公告列表”（接口）
- v15 → 解析“详情页信息”（浏览器+iframe）

---

## ⚡ 快速复现

### 1️⃣ 安装依赖

```bash
pip install requests pandas openpyxl playwright beautifulsoup4
playwright install chromium

### 2️⃣ 运行脚本

python grab_openapi_v3.py
# 或
python fetch_sh_zfcg_v15_format.py

### 3️⃣ 按需求修改日期区间
START_DATE = "2026-03-21"
END_DATE = "2026-03-29"

### 4️⃣ 输出结果
上海采购公告_整合_YYYY-MM-DD.xlsx

🤖 OpenClaw 使用方式（推荐）
### 1️⃣ 将代码放入 workspace
~/.openclaw/workspace/
### 注意：.openclaw是隐藏文件，记得检查是否开启了电脑系统的隐藏文件显示。
在该目录下放入
python grab_openapi_v3.py
python fetch_sh_zfcg_v15_format.py
2️⃣ 直接用自然语言调用
抓取最近一周上海政府采购公告，筛选弱电项目，生成Excel并发送飞书


## 📘 技术实现（Technical Implementation）

本系统采用“接口 + 浏览器自动化 + 文本解析”的组合方案，实现对采购公告的稳定抓取与结构化处理。

---

### 1️⃣ 列表数据获取（接口方式）

采购公告列表通过接口获取，而非网页点击：

```bash
POST https://www.zfcg.sh.gov.cn/portal/category

关键参数：
categoryCode = "ZcyAnnouncement" 采购意向网站
categoryCode = "ZcyAnnouncement2" 采购公告网站

### 实现逻辑：
分页请求接口数据
提取字段：
项目名称（title）
公告日期（publishDate）
articleId（用于拼接详情页）
拼接详情页URL：
detail_url = f"https://www.zfcg.sh.gov.cn/site/detail?parentId=137027&articleId={articleId}"

### 2️⃣ 详情页获取（Playwright）

详情页内容无法通过接口获取，必须通过浏览器解析。

原因：

页面为动态渲染
正文内容位于 iframe 中
页面结构：
主页面（外层DOM）
    ↓
iframe
    ↓
正文内容（真实数据）
实现方式：
frame_locator("iframe.content-container-mapFrame")

步骤：

打开详情页 URL
等待 iframe 加载
获取 iframe 内 body 内容
提取文本

### 3️⃣ 文本解析（核心）

由于页面为非结构化文本：

👉 使用 正则表达式 + 文本匹配 提取字段

关键字段来源：
字段	来源
项目名称	列表页 + 正文
预算金额	项目基本信息
投标要求	申请人的资格要求
报名日期	三、获取采购文件
投标截止时间	四、响应文件提交
联系方式	采购人 / 代理机构
示例：
三、获取采购文件
时间：2026年03月20日至2026年03月25日
四、响应文件提交
截止时间：2026年04月01日 10:00（北京时间）

### 4️⃣ 筛选机制

当前使用关键词匹配：

if "弱电" in 项目名称:
    保留
可扩展方案：
多关键词分类（弱电 / 信息化 / 安防）
正则匹配
排除词过滤
多字段匹配（标题 + 正文）
评分机制
AI分类（推荐）

### 5️⃣ Excel生成

使用 pandas + openpyxl：

流程：
构建 DataFrame
导出 Excel
自动格式化：
列宽调整
自动换行
行高适配
添加超链接

### 6️⃣ 稳定性设计
✔ 使用接口替代网页点击
提升速度
避免页面结构变化影响
✔ 使用 iframe解析
确保获取完整正文
✔ 使用 sleep 控制请求频率

作用：

防止反爬
等待页面加载
提高成功率
✔ 异常处理
页面加载超时处理
数据为空处理
单条失败不影响整体流程

### 7️⃣ OpenClaw 集成（可选）

系统支持接入 OpenClaw：

自动执行抓取任务
自动修改参数（日期/筛选）
自动生成报告
自动发送飞书
使用方式：
抓取最近一周采购公告并生成报告

### 8️⃣ 系统流程总结
接口获取列表
  ↓
筛选项目
  ↓
进入详情页
  ↓
进入 iframe
  ↓
解析文本字段
  ↓
生成 Excel
  ↓
（可选）OpenClaw调用
  ↓
（可选）飞书推送

