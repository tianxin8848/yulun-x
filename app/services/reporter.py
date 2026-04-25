from __future__ import annotations

import re
from datetime import datetime
from io import BytesIO
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas


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


def _resolve_body_font() -> str:
    for candidate in ["/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Medium.ttc"]:
        try:
            pdfmetrics.registerFont(TTFont("CNFont", candidate))
            return "CNFont"
        except Exception:
            continue
    return "Helvetica"


_HEADING_SIZES = {1: 20, 2: 17, 3: 15, 4: 13, 5: 12, 6: 11}


def _strip_inline_markdown(text: str) -> str:
    """去掉行内 **粗体** 标记，保留可见文字。"""
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    t = re.sub(r"\*(.+?)\*", r"\1", t)
    return t


def _classify_markdown_line(raw: str) -> tuple[str, str]:
    """
    返回 (类型, 展示用纯文本)。
    类型: blank | hr | h1..h6 | bullet | num | strong | body
    """
    s = raw.rstrip("\n\r")
    if not s.strip():
        return "blank", ""

    if re.match(r"^[-*_]{3,}\s*$", s.strip()):
        return "hr", ""

    m = re.match(r"^(#{1,6})\s+(.*)$", s)
    if m:
        level = min(len(m.group(1)), 6)
        return f"h{level}", m.group(2).strip()

    stripped = s.strip()
    m = re.match(r"^[-*]\s+(.*)$", stripped)
    if m:
        return "bullet", _strip_inline_markdown(m.group(1).strip())

    m = re.match(r"^\d+\.\s+(.*)$", stripped)
    if m:
        return "num", _strip_inline_markdown(m.group(1).strip())

    m = re.match(r"^\*\*(.+)\*\*$", stripped)
    if m:
        return "strong", m.group(1).strip()

    return "body", _strip_inline_markdown(stripped)


def _wrap_line(text: str, font_name: str, font_size: float, max_width: float) -> list[str]:
    if not text:
        return [""]
    out: list[str] = []
    buf: list[str] = []
    for ch in text:
        probe = "".join(buf) + ch
        if stringWidth(probe, font_name, font_size) <= max_width or not buf:
            buf.append(ch)
        else:
            out.append("".join(buf))
            buf = [ch]
    if buf:
        out.append("".join(buf))
    return out


def render_markdown_to_canvas(c: Canvas, content: str, font_name: str) -> None:
    """把 Markdown 风格正文画到当前 Canvas（分页、标题字号、列表缩进）。"""
    page_w, page_h = A4
    margin_l = 40
    margin_r = 40
    margin_top = 50
    margin_bottom = 60
    max_text_w = page_w - margin_l - margin_r

    y = page_h - margin_top

    def ensure_space(need: float) -> None:
        nonlocal y
        if y < margin_bottom + need:
            c.showPage()
            y = page_h - margin_top

    for raw_line in content.splitlines():
        kind, text = _classify_markdown_line(raw_line)

        if kind == "blank":
            y -= 8
            ensure_space(0)
            continue

        if kind == "hr":
            ensure_space(16)
            c.setLineWidth(0.5)
            c.line(margin_l, y, page_w - margin_r, y)
            y -= 14
            continue

        if kind.startswith("h") and len(kind) == 2 and kind[1].isdigit():
            level = int(kind[1])
            size = _HEADING_SIZES.get(level, 11)
            ensure_space(size * 1.6)
            c.setFont(font_name, size)
            for part in _wrap_line(text, font_name, size, max_text_w):
                ensure_space(size * 1.35)
                c.drawString(margin_l, y, part)
                y -= size * 1.35
            y -= 6
            continue

        indent = margin_l
        font_size = 11.0
        if kind == "bullet":
            indent = margin_l + 14
            text = "· " + text if text else "·"
        elif kind == "num":
            indent = margin_l + 14
        elif kind == "strong":
            font_size = 12.5

        c.setFont(font_name, font_size)
        for part in _wrap_line(text, font_name, font_size, max_text_w - (indent - margin_l)):
            ensure_space(font_size * 1.35)
            c.drawString(indent, y, part)
            y -= font_size * 1.3

        if kind in ("bullet", "num", "strong"):
            y -= 2


def save_pdf(content: str, filename: str) -> str:
    report_dir = ensure_report_dirs()
    path = report_dir / filename
    font_name = _resolve_body_font()
    c = Canvas(str(path), pagesize=A4)
    render_markdown_to_canvas(c, content, font_name)
    c.save()
    return str(path)


def text_to_pdf_bytes(content: str) -> bytes:
    """将 Markdown 正文写入 PDF（标题分级、列表、整行粗体），返回字节流。"""
    buffer = BytesIO()
    font_name = _resolve_body_font()
    c = Canvas(buffer, pagesize=A4)
    render_markdown_to_canvas(c, content, font_name)
    c.save()
    return buffer.getvalue()
