# 舆情获取 + 分析系统（Python + PostgreSQL）

这是一个可运行的 MVP：
- 输入关键词，抓取 Google News 中文 RSS。
- 使用 SnowNLP 做情感分析，jieba 提取关键词。
- 调用 DeepSeek 生成中文舆情简报（可选）。
- 结果写入 PostgreSQL，并生成 Markdown + PDF 报告。

## 1) 启动 PostgreSQL（Docker + 持久化）

```bash
cp .env.example .env
docker compose up -d
```

持久化说明：
- `docker-compose.yml` 使用命名卷 `postgres_data` 挂载到 `/var/lib/postgresql/data`。
- 即使容器删除重建，数据仍保留在该卷里。

## 2) 安装 Python 依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3) 配置 DeepSeek（可选）

编辑 `.env`：
- `DEEPSEEK_API_KEY=你的key`

你给的 `deepseekapi.txt` 中 key 已经可用，建议复制到 `.env`，不要硬编码到代码里。

## 4) 初始化数据库

```bash
python scripts/init_db.py
```

## 5) 运行 Web 界面

```bash
streamlit run streamlit_app.py
```

打开页面后输入关键词（如“香港AI新闻”），点击“生成今日报告”。

---

## 表结构设计（PostgreSQL）

### `runs`
- `id`：主键
- `keyword`：本次任务关键词（索引）
- `created_at`：任务创建时间
- `summary`：DeepSeek 生成的总览总结

### `articles`
- `id`：主键
- `run_id`：关联 `runs.id`
- `title`：新闻标题
- `source`：来源
- `source_url`：新闻链接
- `published_at`：发布时间
- `content`：摘要内容
- `sentiment_score`：情感分值（0-1）
- `sentiment_label`：情感标签（positive/neutral/negative）
- `keywords`：文章关键词（逗号分隔）
- `created_at`：入库时间
- 约束：`(run_id, source_url)` 唯一，防止同次任务重复

### `reports`
- `id`：主键
- `run_id`：关联 `runs.id`（一对一）
- `markdown_path`：md 报告文件路径
- `pdf_path`：pdf 报告文件路径
- `created_at`：生成时间

## 后续可扩展
- 加入 X/微博数据源（注意合规与限频）。
- 用 APScheduler 或 cron 每天早上自动执行并推送报告。
- 加入高级中文模型进行主题聚类、事件链路和风险评分。
