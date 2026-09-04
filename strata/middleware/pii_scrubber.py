from __future__ import annotations

import json
import re

from starlette.types import ASGIApp, Receive, Scope, Send

PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b[A-CEGHJ-PR-TW-Z]{2}\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]\b"), "[REDACTED]"),
    (re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}\b"), "[REDACTED]"),
    (re.compile(r"\bMR\s+[A-Z]+\s+[A-Z]+\s+\d{1,2}\s+\d{1,2}\b"), "[REDACTED]"),
    (re.compile(r"\bMS\s+[A-Z]+\s+[A-Z]+\s+\d{1,2}\s+\d{1,2}\b"), "[REDACTED]"),
]


def scrub_pii(text: str) -> tuple[str, int]:
    redacted = 0
    for pattern, replacement in PATTERNS:
        new_text, count = pattern.subn(replacement, text)
        if count > 0:
            redacted += count
            text = new_text
    return text, redacted


class PIIScrubber:
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

        is_streaming = data.get("stream", False)

        async def receive_cached():
            return {"type": "http.request", "body": body, "more_body": False}

        if is_streaming:
            await self.app(scope, receive_cached, send)
            return

        collected_body = b""
        status_code = 200
        resp_headers: list[list[bytes]] = []

        async def send_collect(message: dict) -> None:
            nonlocal collected_body, status_code, resp_headers
            if message["type"] == "http.response.start":
                status_code = message["status"]
                resp_headers = message.get("headers", [])
                await send(message)
            elif message["type"] == "http.response.body":
                collected_body += message.get("body", b"")
                if not message.get("more_body", False):
                    scrubbed = self._scrub_response(collected_body)
                    await send({
                        "type": "http.response.body",
                        "body": scrubbed,
                        "more_body": False,
                    })

        await self.app(scope, receive_cached, send_collect)

    def _scrub_response(self, response_body: bytes) -> bytes:
        try:
            body_dict = json.loads(response_body)
        except (json.JSONDecodeError, ValueError):
            return response_body

        if "choices" not in body_dict:
            return response_body

        total_redacted = 0
        for choice in body_dict.get("choices", []):
            message = choice.get("message", {})
            content = message.get("content")
            if content and isinstance(content, str):
                redacted_content, count = scrub_pii(content)
                if count > 0:
                    message["content"] = redacted_content
                    total_redacted += count

        if total_redacted > 0:
            body_dict.setdefault("strata", {})["redacted_tokens"] = total_redacted
            return json.dumps(body_dict).encode()
        return response_body
