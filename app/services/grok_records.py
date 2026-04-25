from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import bindparam, text

from app.db import engine


def fetch_grok_chat_records(limit: int = 300) -> list[dict[str, Any]]:
    """从 grok_chat_records 读取最近记录，供界面展示与多选。"""
    sql = text(
        """
        SELECT id, platform, conversation_id, source, page_url,
               question, answer, captured_at, created_at
        FROM grok_chat_records
        ORDER BY captured_at DESC NULLS LAST, id DESC
        LIMIT :lim
        """
    )
    rows: list[dict[str, Any]] = []
    try:
        with engine.connect() as conn:
            result = conn.execute(sql, {"lim": limit})
            for r in result.mappings().all():
                row = dict(r)
                for k in ("captured_at", "created_at"):
                    v = row.get(k)
                    if isinstance(v, datetime):
                        row[k] = v.isoformat()
                rows.append(row)
    except Exception:
        return []
    return rows


def fetch_grok_records_by_ids(ids: list[int]) -> list[dict[str, Any]]:
    if not ids:
        return []
    sql = text(
        """
        SELECT id, platform, conversation_id, source, page_url,
               question, answer, captured_at, created_at
        FROM grok_chat_records
        WHERE id IN :ids
        ORDER BY captured_at ASC NULLS LAST, id ASC
        """
    ).bindparams(bindparam("ids", expanding=True))
    rows: list[dict[str, Any]] = []
    try:
        with engine.connect() as conn:
            result = conn.execute(sql, {"ids": list(dict.fromkeys(ids))})
            for r in result.mappings().all():
                row = dict(r)
                for k in ("captured_at", "created_at"):
                    v = row.get(k)
                    if isinstance(v, datetime):
                        row[k] = v.isoformat()
                rows.append(row)
    except Exception:
        return []
    return rows
