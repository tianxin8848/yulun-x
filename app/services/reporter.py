from __future__ import annotations

from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


def ensure_report_dirs() -> Path:
    root = Path("reports")
    root.mkdir(parents=True, exist_ok=True)
    return root


def build_markdown(
    keyword: str,
    run_time: datetime,
    summary: str,
    sentiment_distribution: dict[str, int],
    top_keywords: list[str],
    article_titles: list[str],
) -> str:
    return "\n".join(
        [
            f"# 舆情日报：{keyword}",
            "",
            f"- 生成时间：{run_time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 智能总结",
            summary,
            "",
            "## 情感分布",
            f"- 正面：{sentiment_distribution.get('positive', 0)}",
            f"- 中性：{sentiment_distribution.get('neutral', 0)}",
            f"- 负面：{sentiment_distribution.get('negative', 0)}",
            "",
            "## 高频关键词",
            ", ".join(top_keywords) if top_keywords else "无",
            "",
            "## 重点资讯",
            *[f"- {title}" for title in article_titles[:20]],
            "",
        ]
    )


def save_markdown(content: str, filename: str) -> str:
    report_dir = ensure_report_dirs()
    path = report_dir / filename
    path.write_text(content, encoding="utf-8")
    return str(path)


def save_pdf(content: str, filename: str) -> str:
    report_dir = ensure_report_dirs()
    path = report_dir / filename
    c = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4

    font_name = "Helvetica"
    for candidate in ["/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Medium.ttc"]:
        try:
            pdfmetrics.registerFont(TTFont("CNFont", candidate))
            font_name = "CNFont"
            break
        except Exception:
            continue

    c.setFont(font_name, 11)
    y = height - 50
    for raw_line in content.splitlines():
        line = raw_line[:95]
        c.drawString(40, y, line)
        y -= 16
        if y < 60:
            c.showPage()
            c.setFont(font_name, 11)
            y = height - 50
    c.save()
    return str(path)
