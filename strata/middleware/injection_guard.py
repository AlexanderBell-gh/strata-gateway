from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from starlette.types import ASGIApp, Receive, Scope, Send

from strata.telemetry.logger import log_telemetry
from strata.models.schemas import TelemetryEvent

INJECTION_KEYWORDS = [
    "ignore all prior",
    "ignore previous instructions",
    "override previous instructions",
    "system prompt:",
    "secret key",
    "api_key",
    "password=",
    "extract my credentials",
    "don't follow rules",
    "disregard all instructions",
    "you are now",
    "new instructions:",
    "forget everything",
]


def detect_injection(text: str) -> str | None:
    text_lower = text.lower()
    for kw in INJECTION_KEYWORDS:
        if kw in text_lower:
            return kw
    return None


class InjectionGuard:
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

        messages = data.get("messages", [])
        for msg in messages:
            content = msg.get("content") or ""
            matched = detect_injection(content)
            if matched:
                request_id = str(uuid.uuid4())
                await log_telemetry(
                    TelemetryEvent(
                        request_id=request_id,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        agent_id=data.get("agent_id"),
                        session_id=data.get("session_id"),
                        model=data.get("model", "unknown"),
                        tokens_in=0,
                        tokens_out=0,
                        latency_ms=0,
                        status_code=403,
                        upstream_url="",
                        sub_status="injection_blocked",
                    )
                )
                error_body = json.dumps({
                    "error": {
                        "code": "injection_blocked",
                        "message": "Prompt injection detected — request blocked by Strata",
                        "details": {
                            "pattern_matched": matched,
                            "request_id": request_id,
                        },
                    }
                }).encode()
                await send({
                    "type": "http.response.start",
                    "status": 403,
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

        async def receive_cached():
            return {"type": "http.request", "body": body, "more_body": False}

        scope.setdefault("asgi", {})["spec_version"] = "2.4"
        await self.app(scope, receive_cached, send)
