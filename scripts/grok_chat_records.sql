CREATE TABLE IF NOT EXISTS grok_chat_records (
    id BIGSERIAL PRIMARY KEY,
    platform VARCHAR(32) NOT NULL DEFAULT 'x_grok',
    conversation_id VARCHAR(128) NOT NULL,
    source VARCHAR(16) NOT NULL DEFAULT 'manual',
    page_url TEXT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    question_hash CHAR(64) NOT NULL,
    answer_hash CHAR(64) NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_grok_chat_records_conversation_id
    ON grok_chat_records (conversation_id);

CREATE INDEX IF NOT EXISTS idx_grok_chat_records_captured_at
    ON grok_chat_records (captured_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS uq_grok_chat_records_message_fingerprint
    ON grok_chat_records (conversation_id, question_hash, answer_hash);

COMMENT ON TABLE grok_chat_records IS 'Store Grok latest Q&A captured by Tampermonkey script.';
COMMENT ON COLUMN grok_chat_records.source IS 'manual: button click, auto: mutation observer upload.';
