import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestHealth:
    async def test_health_returns_ok(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestChatCompletionsNonStreaming:
    @patch("strata.core.proxy.log_telemetry", new_callable=AsyncMock)
    @patch("strata.core.proxy.get_client")
    async def test_proxy_forwards_request(self, mock_get_client, mock_log, client):
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
            "stream": False,
        }
        resp = await client.post("/v1/chat/completions", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "chatcmpl-123"
        assert "strata" in body
        assert "request_id" in body["strata"]
        assert "latency_ms" in body["strata"]
        mock_log.assert_called_once()

    @patch("strata.core.proxy.get_client")
    async def test_upstream_error_returns_502(self, mock_get_client, client):
        mock_httpx = AsyncMock()
        mock_httpx.post = AsyncMock(side_effect=Exception("connection refused"))
        mock_get_client.return_value = mock_httpx

        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hi"}],
        }
        resp = await client.post("/v1/chat/completions", json=payload)
        assert resp.status_code == 502
        assert "error" in resp.json()


class TestChatCompletionsStreaming:
    @patch("strata.core.proxy.log_telemetry", new_callable=AsyncMock)
    @patch("strata.core.proxy.get_client")
    async def test_stream_yields_sse_chunks(self, mock_get_client, mock_log, client):
        async def mock_aiter_lines():
            for chunk in [
                'data: {"id":"chatcmpl-1","choices":[{"delta":{"content":"Hi"}}]}',
                'data: {"id":"chatcmpl-1","choices":[{"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":5,"completion_tokens":1}}',
                "data: [DONE]",
            ]:
                yield chunk

        class FakeStreamContext:
            async def __aenter__(self):
                self._stream = MagicMock()
                self._stream.aiter_lines = mock_aiter_lines
                self._stream.status_code = 200
                self._stream.aread = AsyncMock(return_value=b"")
                return self._stream

            async def __aexit__(self, *args):
                pass

        mock_httpx = AsyncMock()
        mock_httpx.stream = MagicMock(return_value=FakeStreamContext())
        mock_get_client.return_value = mock_httpx

        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hi"}],
            "stream": True,
        }
        resp = await client.post("/v1/chat/completions", json=payload)
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

        lines = resp.text.split("\n\n")
        data_lines = [l for l in lines if l.startswith("data:")]
        assert len(data_lines) >= 3
        mock_log.assert_called_once()


class TestModels:
    @patch("strata.core.proxy.get_client")
    async def test_models_passthrough(self, mock_get_client, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": [{"id": "gpt-4", "object": "model"}]
        }
        mock_httpx = AsyncMock()
        mock_httpx.get = AsyncMock(return_value=mock_resp)
        mock_get_client.return_value = mock_httpx

        resp = await client.get("/v1/models")
        assert resp.status_code == 200
        assert "data" in resp.json()

    @patch("strata.core.proxy.get_client")
    async def test_models_upstream_error_returns_502(self, mock_get_client, client):
        mock_httpx = AsyncMock()
        mock_httpx.get = AsyncMock(side_effect=Exception("connection refused"))
        mock_get_client.return_value = mock_httpx

        resp = await client.get("/v1/models")
        assert resp.status_code == 502
        body = resp.json()
        assert "error" in body
        assert body["error"]["code"] == "upstream_error"


class TestConcurrency:
    @patch("strata.core.proxy.log_telemetry", new_callable=AsyncMock)
    @patch("strata.core.proxy.get_client")
    async def test_concurrent_requests(self, mock_get_client, mock_log, client):
        import asyncio

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
            "stream": False,
        }

        tasks = [
            client.post("/v1/chat/completions", json=payload)
            for _ in range(50)
        ]
        results = await asyncio.gather(*tasks)

        for resp in results:
            assert resp.status_code == 200
            assert "strata" in resp.json()

        assert mock_log.call_count == 50
