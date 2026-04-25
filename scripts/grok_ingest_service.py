from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)


def parse_ts(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    ts = value.replace("Z", "+00:00")
    return datetime.fromisoformat(ts)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def insert_record(payload: dict) -> int | None:
    question = (payload.get("question") or "").strip()
    answer = (payload.get("answer") or "").strip()
    if not question or not answer:
        raise ValueError("question / answer is empty")

    source = (payload.get("source") or "manual").strip() or "manual"
    conversation_id = (payload.get("conversation_id") or "").strip()
    page_url = (payload.get("page_url") or "").strip()
    captured_at = parse_ts(payload.get("captured_at"))
    q_hash = sha256_hex(question)
    a_hash = sha256_hex(answer)

    sql = text(
        """
        INSERT INTO grok_chat_records (
            platform, conversation_id, source, page_url,
            question, answer, question_hash, answer_hash, captured_at
        ) VALUES (
            :platform, :conversation_id, :source, :page_url,
            :question, :answer, :question_hash, :answer_hash, :captured_at
        )
        ON CONFLICT (conversation_id, question_hash, answer_hash) DO NOTHING
        RETURNING id
        """
    )
    values = {
        "platform": payload.get("platform") or "x_grok",
        "conversation_id": conversation_id,
        "source": source,
        "page_url": page_url,
        "question": question,
        "answer": answer,
        "question_hash": q_hash,
        "answer_hash": a_hash,
        "captured_at": captured_at,
    }
    with engine.begin() as conn:
        row = conn.execute(sql, values).fetchone()
        return int(row[0]) if row else None


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, body: dict) -> None:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.end_headers()
        self.wfile.write(encoded)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send_json(200, {"ok": True})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/grok/messages":
            self._send_json(404, {"ok": False, "error": "not found"})
            return

        try:
            content_len = int(self.headers.get("Content-Length") or "0")
            raw = self.rfile.read(content_len).decode("utf-8")
            payload = json.loads(raw or "{}")
            saved_id = insert_record(payload)
            self._send_json(200, {"ok": True, "id": saved_id, "deduped": saved_id is None})
        except Exception as exc:  # noqa: BLE001
            self._send_json(400, {"ok": False, "error": str(exc)})


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 8000), Handler)
    print("Grok ingest service running: http://127.0.0.1:8000")
    server.serve_forever()
