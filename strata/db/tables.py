from strata.db.engine import get_db

TELEMETRY_TABLE = """
CREATE TABLE IF NOT EXISTS telemetry (
    request_id  TEXT PRIMARY KEY,
    timestamp   TEXT NOT NULL,
    agent_id    TEXT,
    session_id  TEXT,
    model       TEXT NOT NULL,
    tokens_in   INTEGER DEFAULT 0,
    tokens_out  INTEGER DEFAULT 0,
    redacted_tokens INTEGER DEFAULT 0,
    latency_ms  REAL DEFAULT 0,
    status_code INTEGER DEFAULT 200,
    upstream_url TEXT NOT NULL,
    sub_status  TEXT DEFAULT ''
);
"""

MIGRATIONS = [
    "ALTER TABLE telemetry ADD COLUMN redacted_tokens INTEGER DEFAULT 0",
    "ALTER TABLE telemetry ADD COLUMN sub_status TEXT DEFAULT ''",
]

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_telemetry_agent ON telemetry(agent_id);",
    "CREATE INDEX IF NOT EXISTS idx_telemetry_session ON telemetry(session_id);",
    "CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp ON telemetry(timestamp);",
]


async def init_tables() -> None:
    db = await get_db()
    await db.execute(TELEMETRY_TABLE)
    for migration in MIGRATIONS:
        try:
            await db.execute(migration)
        except Exception:
            pass
    for idx in INDEXES:
        await db.execute(idx)
    await db.commit()
