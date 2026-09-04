from __future__ import annotations

import json
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable

from starlette.types import ASGIApp, Receive, Scope, Send

from strata.config import settings
from strata.models.schemas import TelemetryEvent
from strata.telemetry.logger import log_telemetry


class CircuitBreakerState:
    def __init__(self) -> None:
        self.tokens_per_session: dict[str, int] = defaultdict(int)

    def reset(self, session_id: str) -> None:
        self.tokens_per_session.pop(session_id, None)


_state: CircuitBreakerState | None = None


def get_circuit_breaker_state() -> CircuitBreakerState:
    global _state
    if _state is None:
        _state = CircuitBreakerState()
    return _state


class CircuitBreaker:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] != "/v1/chat/completions":
            await self.app(scope, receive, send)
            return

        body = b""
        while True:
            message = await receive()
            body += message.get("body", b"")
            if not message.get("more_body", False):
                break

        try:
            data = json.loads(body) if body else {}
        except (json.JSONDecodeError, ValueError):
            data = {}

        session_id = data.get("session_id") or "unknown"
        state = get_circuit_breaker_state()

        if state.tokens_per_session[session_id] >= settings.STRATA_MAX_TOKENS_PER_SESSION:
            request_id = str(uuid.uuid4())
            await log_telemetry(
                TelemetryEvent(
                    request_id=request_id,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    agent_id=data.get("agent_id"),
                    session_id=session_id,
                    model=data.get("model", "unknown"),
                    tokens_in=0,
                    tokens_out=0,
                    latency_ms=0,
                    status_code=429,
                    upstream_url="",
                    sub_status="circuit_open",
                )
            )
            error_body = json.dumps({
                "error": {
                    "code": "circuit_open",
                    "message": f"Token spending limit reached for session ({settings.STRATA_MAX_TOKENS_PER_SESSION} tokens)",
                    "details": {
                        "session_id": session_id,
                        "tokens_used": state.tokens_per_session[session_id],
                        "limit": settings.STRATA_MAX_TOKENS_PER_SESSION,
                        "request_id": request_id,
                    },
                }
            }).encode()
            await send({
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    [b"content-type", b"application/json"],
                    [b"content-length", str(len(error_body)).encode()],
                ],
            })
            await send({
                "type": "http.response.body",
                "body": error_body,
            })
            return

        is_streaming = data.get("stream", False)
        response_started = False
        response_body = b""
        is_stream_response = False

        async def receive_cached():
            return {"type": "http.request", "body": body, "more_body": False}

        async def send_wrapped(message: dict) -> None:
            nonlocal response_started, response_body, is_stream_response
            if message["type"] == "http.response.start":
                response_started = True
                headers = message.get("headers", [])
                for h in headers:
                    if h[0] == b"content-type" and b"text/event-stream" in h[1]:
                        is_stream_response = True
                        break
                await send(message)
            elif message["type"] == "http.response.body":
                if is_stream_response:
                    await send(message)
                else:
                    response_body += message.get("body", b"")
                    if not message.get("more_body", False):
                        try:
                            body_dict = json.loads(response_body)
                            usage = body_dict.get("usage", {})
                            tokens_out = usage.get("completion_tokens", 0)
                            if tokens_out > 0:
                                state.tokens_per_session[session_id] += tokens_out
                        except (json.JSONDecodeError, ValueError):
                            pass
                    await send(message)

        scope.setdefault("asgi", {})["spec_version"] = "2.4"
        await self.app(scope, receive_cached, send_wrapped)
