import os

os.environ.setdefault("STRATA_UPSTREAM_API_KEY", "sk-test-dummy")

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from strata.middleware.pii_scrubber import scrub_pii
from strata.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestScrubPii:
    def test_scrubs_ni_number(self):
        text, count = scrub_pii("My NI is AB 12 34 56 C")
        assert "[REDACTED]" in text
        assert count == 1

    def test_scrubs_postcode(self):
        text, count = scrub_pii("I live in SW1A 1AA")
        assert "[REDACTED]" in text
        assert count == 1

    def test_scrubs_mr_name_dob(self):
        text, count = scrub_pii("MR JOHN SMITH 01 01")
        assert "[REDACTED]" in text
        assert count == 1

    def test_scrubs_ms_name_dob(self):
        text, count = scrub_pii("MS JANE DOE 15 03")
        assert "[REDACTED]" in text
        assert count == 1

    def test_no_pii_returns_unchanged(self):
        text, count = scrub_pii("Hello, how are you?")
        assert text == "Hello, how are you?"
        assert count == 0

    def test_multiple_pii(self):
        text, count = scrub_pii("NI: AB123456C, postcode: SW1A1AA")
        assert text.count("[REDACTED]") == 2
        assert count == 2


class TestPIIScrubberNonStreaming:
    @patch("strata.core.proxy.log_telemetry", new_callable=AsyncMock)
    @patch("strata.core.proxy.get_client")
    async def test_scrubs_pii_from_response(self, mock_get_client, mock_log, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1700000000,
            "model": "gpt-4",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Your NI number is AB 12 34 56 C"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_resp.status_code = 200
        mock_httpx = AsyncMock()
        mock_httpx.post = AsyncMock(return_value=mock_resp)
        mock_get_client.return_value = mock_httpx

        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "What is my NI number?"}],
        }
        resp = await client.post("/v1/chat/completions", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert "[REDACTED]" in body["choices"][0]["message"]["content"]
        assert body["strata"]["redacted_tokens"] == 1

    @patch("strata.core.proxy.log_telemetry", new_callable=AsyncMock)
    @patch("strata.core.proxy.get_client")
    async def test_clean_response_unchanged(self, mock_get_client, mock_log, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1700000000,
            "model": "gpt-4",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hello!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_resp.status_code = 200
        mock_httpx = AsyncMock()
        mock_httpx.post = AsyncMock(return_value=mock_resp)
        mock_get_client.return_value = mock_httpx

        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hi"}],
        }
        resp = await client.post("/v1/chat/completions", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["choices"][0]["message"]["content"] == "Hello!"
        assert "redacted_tokens" not in body.get("strata", {})
