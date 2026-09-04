import os

os.environ.setdefault("STRATA_UPSTREAM_API_KEY", "sk-test-dummy")
os.environ.setdefault("STRATA_MAX_TOKENS_PER_SESSION", "50")

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from strata.main import app
from strata.middleware.circuit_breaker import get_circuit_breaker_state


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def reset_circuit_breaker(monkeypatch):
    monkeypatch.setattr("strata.config.settings.STRATA_MAX_TOKENS_PER_SESSION", 50)
    state = get_circuit_breaker_state()
    state.reset("test-session")
    state.reset("tracked-session")
    yield
    state.reset("test-session")
    state.reset("tracked-session")


class TestCircuitBreaker:
    @patch("strata.core.proxy.log_telemetry", new_callable=AsyncMock)
    @patch("strata.core.proxy.get_client")
    async def test_allows_request_under_limit(self, mock_get_client, mock_log, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1700000000,
            "model": "gpt-4",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hi!"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_resp.status_code = 200
        mock_httpx = AsyncMock()
        mock_httpx.post = AsyncMock(return_value=mock_resp)
        mock_get_client.return_value = mock_httpx

        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hi"}],
            "session_id": "test-session",
        }
        resp = await client.post("/v1/chat/completions", json=payload)
        assert resp.status_code == 200

    @patch("strata.middleware.circuit_breaker.log_telemetry", new_callable=AsyncMock)
    @patch("strata.core.proxy.log_telemetry", new_callable=AsyncMock)
    @patch("strata.core.proxy.get_client")
    async def test_blocks_when_limit_exceeded(self, mock_get_client, mock_log, mock_cb_log, client):
        state = get_circuit_breaker_state()
        state.tokens_per_session["test-session"] = 50

        mock_httpx = AsyncMock()
        mock_get_client.return_value = mock_httpx

        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hi"}],
            "session_id": "test-session",
        }
        resp = await client.post("/v1/chat/completions", json=payload)
        assert resp.status_code == 429
        body = resp.json()
        assert body["error"]["code"] == "circuit_open"
        mock_httpx.post.assert_not_called()

    @patch("strata.core.proxy.log_telemetry", new_callable=AsyncMock)
    @patch("strata.core.proxy.get_client")
    async def test_no_session_uses_unknown(self, mock_get_client, mock_log, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1700000000,
            "model": "gpt-4",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hi!"}, "finish_reason": "stop"}],
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

    @patch("strata.middleware.circuit_breaker.log_telemetry", new_callable=AsyncMock)
    @patch("strata.core.proxy.log_telemetry", new_callable=AsyncMock)
    @patch("strata.core.proxy.get_client")
    async def test_tracks_tokens_across_requests(self, mock_get_client, mock_log, mock_cb_log, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1700000000,
            "model": "gpt-4",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hi!"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 30, "total_tokens": 40},
        }
        mock_resp.status_code = 200
        mock_httpx = AsyncMock()
        mock_httpx.post = AsyncMock(return_value=mock_resp)
        mock_get_client.return_value = mock_httpx

        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hi"}],
            "session_id": "tracked-session",
        }

        resp1 = await client.post("/v1/chat/completions", json=payload)
        assert resp1.status_code == 200

        resp2 = await client.post("/v1/chat/completions", json=payload)
        assert resp2.status_code == 200

        resp3 = await client.post("/v1/chat/completions", json=payload)
        assert resp3.status_code == 429
        assert resp3.json()["error"]["code"] == "circuit_open"
