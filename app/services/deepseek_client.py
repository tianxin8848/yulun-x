from __future__ import annotations

from typing import Any

import requests

from app.config import settings


def summarize(keyword: str, articles: list[dict[str, Any]]) -> str:
    if not settings.deepseek_api_key:
        return "未配置 DeepSeek API Key，已跳过智能总结。"
    if not articles:
        return "没有可用于总结的新闻数据。"

    bullets = []
    for item in articles[:12]:
        bullets.append(f"- 标题：{item.get('title', '')}\n  摘要：{item.get('content', '')[:180]}")
    prompt = (
        f"请你作为中文舆情分析师，围绕关键词“{keyword}”输出今日简报：\n"
        "1) 关键事件3条\n2) 情绪走向\n3) 风险提示\n4) 后续观察点。\n"
        "要求：使用简洁中文，使用项目符号，控制在300字以内。\n\n原始资讯：\n"
        + "\n".join(bullets)
    )

    url = f"{settings.deepseek_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.deepseek_model,
        "messages": [
            {"role": "system", "content": "你是专业中文舆情分析助手。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=45)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        return f"DeepSeek 总结失败：{exc}"
