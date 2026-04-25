-- DeepSeek 根据所选 Grok 问答生成的领导参阅报告存档
CREATE TABLE IF NOT EXISTS grok_leadership_reports (
    id BIGSERIAL PRIMARY KEY,
    source_grok_ids JSONB NOT NULL,
    report_body TEXT NOT NULL,
    deepseek_model VARCHAR(128) NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_grok_leadership_reports_created_at
    ON grok_leadership_reports (created_at DESC);

COMMENT ON TABLE grok_leadership_reports IS 'Leadership-oriented reports generated from selected grok_chat_records via DeepSeek.';
COMMENT ON COLUMN grok_leadership_reports.source_grok_ids IS 'JSON array of grok_chat_records.id, in selection order.';
