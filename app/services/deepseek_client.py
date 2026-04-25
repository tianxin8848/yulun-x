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


def generate_leadership_report_from_grok(records: list[dict[str, Any]]) -> str:
    """
    根据选中的 Grok 问答记录，生成面向中国领导的正式书面报告。
    records 每项建议包含：id, captured_at, page_url, question, answer, platform（可选）
    """
    if not settings.deepseek_api_key:
        return "未配置 DeepSeek API Key，无法生成报告。请在环境变量中设置 DEEPSEEK_API_KEY。"
    if not records:
        return "请至少选择一条对话记录后再生成报告。"

    blocks = []
    for i, row in enumerate(records, start=1):
        cap = row.get("captured_at") or ""
        src = row.get("page_url") or ""
        plat = row.get("platform") or "x_grok"
        q = (row.get("question") or "").strip()
        a = (row.get("answer") or "").strip()
        blocks.append(
            f"【材料 {i}】\n"
            f"- 采集时间（系统记录）：{cap}\n"
            f"- 信息来源（页面/平台）：{plat}；链接：{src}\n"
            f"- 用户提问：\n{q}\n"
            f"- 模型回答（原文摘录，请据此归纳，勿编造材料外事实）：\n{a[:12000]}{'…（已截断）' if len(a) > 12000 else ''}\n"
        )

    user_prompt = (
        "以下材料来自本系统采集的 Grok 对话（每条含采集时间、来源链接、提问与回答原文）。\n\n"
        + "\n".join(blocks)
        + "\n请基于以上材料撰写一份**给中国领导阅读**的内部参阅报告。"
    )

    system_prompt = (
        "你是资深政策与舆情研究顾问，文风庄重、准确、可归档。\n"
        "写作要求：\n"
        "1）报告须结构化（建议含：概述、分条要点、信息来源说明、局限与建议）。\n"
        "2）凡涉及事件，尽量写明**具体时间**（可来自材料中的日期/时间表述或采集时间）、**地点**或地域范围；"
        "材料中无法确定的，须明确写“材料未载明”或“待核实”，**禁止编造**。\n"
        "3）**信息来源**必须可追溯：每条重要结论或事实后，用括号注明对应材料序号及来源（如：材料1，采集时间…；链接…）。\n"
        "4）若材料为二手转述或模型推断，须区分“事实陈述”与“模型观点”，避免把推测当定论。\n"
        "5）使用规范书面中文，篇幅适中（建议 800～2000 字），便于领导批阅。"
    )

    url = f"{settings.deepseek_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.deepseek_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.25,
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        return f"DeepSeek 生成报告失败：{exc}"
