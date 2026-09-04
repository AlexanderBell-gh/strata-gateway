import logging

from strata.db.engine import get_db
from strata.models.schemas import TelemetryEvent

logger = logging.getLogger("strata.telemetry")


async def log_telemetry(event: TelemetryEvent) -> None:
    db = await get_db()
    await db.execute(
        """INSERT INTO telemetry
           (request_id, timestamp, agent_id, session_id, model,
            tokens_in, tokens_out, redacted_tokens, latency_ms, status_code,
            upstream_url, sub_status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            event.request_id,
            event.timestamp,
            event.agent_id,
            event.session_id,
            event.model,
            event.tokens_in,
            event.tokens_out,
            event.redacted_tokens,
            event.latency_ms,
            event.status_code,
            event.upstream_url,
            event.sub_status,
        ),
    )
    await db.commit()
    logger.debug("Telemetry logged: %s", event.request_id)
