import json
import time
import uuid
from datetime import datetime, timezone

import httpx

from strata.config import settings
from strata.models.schemas import ProxyRequest, TelemetryEvent
from strata.telemetry.logger import log_telemetry

_client: httpx.AsyncClient | None = None


async def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.STRATA_TIMEOUT),
            limits=httpx.Limits(
                max_connections=settings.STRATA_MAX_CONCURRENT,
                max_keepalive_connections=settings.STRATA_MAX_CONCURRENT // 2,
            ),
        )
    return _client


async def close_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None


def _upstream_url() -> str:
    return f"{settings.STRATA_DEFAULT_UPSTREAM}/chat/completions"


def _upstream_models_url() -> str:
    return f"{settings.STRATA_DEFAULT_UPSTREAM}/models"


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.STRATA_UPSTREAM_API_KEY}"}


def _upstream_body(request: ProxyRequest) -> dict:
    body = request.model_dump(exclude={"agent_id", "session_id"})
    return body


async def proxy_request(request: ProxyRequest) -> dict:
    request_id = str(uuid.uuid4())
    start = time.monotonic()

    client = await get_client()
    resp = await client.post(
        _upstream_url(),
        json=_upstream_body(request),
        headers=_auth_headers(),
    )

    latency_ms = (time.monotonic() - start) * 1000
    body = resp.json()

    usage = body.get("usage") or {}
    await log_telemetry(
        TelemetryEvent(
            request_id=request_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent_id=request.agent_id,
            session_id=request.session_id,
            model=request.model,
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
            latency_ms=latency_ms,
            status_code=resp.status_code,
            upstream_url=settings.STRATA_DEFAULT_UPSTREAM,
        )
    )

    body["strata"] = {
        "request_id": request_id,
        "latency_ms": latency_ms,
        "upstream_model": body.get("model", request.model),
    }
    return body


async def proxy_stream(request: ProxyRequest):
    request_id = str(uuid.uuid4())
    start = time.monotonic()
    usage: dict = {}

    client = await get_client()
    async with client.stream(
        "POST",
        _upstream_url(),
        json={**_upstream_body(request), "stream": True},
        headers=_auth_headers(),
    ) as upstream:
        async for line in upstream.aiter_lines():
            if line.startswith("data: "):
                chunk_data = line[6:]
                if chunk_data.strip() == "[DONE]":
                    yield f"data: [DONE]\n\n"
                    break
                try:
                    chunk = json.loads(chunk_data)
                    if chunk.get("usage"):
                        usage = chunk["usage"]
                except json.JSONDecodeError:
                    pass
                yield f"{line}\n\n"
        else:
            yield f"data: [DONE]\n\n"

    latency_ms = (time.monotonic() - start) * 1000
    await log_telemetry(
        TelemetryEvent(
            request_id=request_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent_id=request.agent_id,
            session_id=request.session_id,
            model=request.model,
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
            latency_ms=latency_ms,
            status_code=200,
            upstream_url=settings.STRATA_DEFAULT_UPSTREAM,
        )
    )


async def list_models() -> dict:
    client = await get_client()
    resp = await client.get(
        _upstream_models_url(),
        headers=_auth_headers(),
    )
    return resp.json()
