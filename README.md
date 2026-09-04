# Strata Gateway

A high-performance, security-focused API gateway and governance proxy designed to safely manage, sandbox, and monitor autonomous AI agents.

Strata sits between AI agent frameworks (LangChain, AutoGen, CrewAI) and frontier LLM providers, acting as a semantic firewall that traditional network firewalls cannot provide. It prevents data leaks, halts rogue recursive behaviours, and enforces programmatic compliance with UK-specific legislation.

## Quick Start

```bash
# Clone and install
git clone git@github.com:AlexanderBell-gh/strata-gateway.git
cd strata-gateway
uv sync

# Configure
cp .env.example .env
# Edit .env and set STRATA_UPSTREAM_API_KEY

# Run
uv run uvicorn strata.main:app --reload
```

The proxy starts on `http://localhost:8000`.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/chat/completions` | Proxy chat completion request to upstream LLM |
| `GET` | `/v1/models` | List available models from upstream |
| `GET` | `/health` | Health check — returns `200 OK` |

All endpoints are versioned under `/v1/` to match the OpenAI SDK convention. Point your agent's `base_url` at Strata with zero code changes:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="your-key",  # Strata ignores this, injects real key server-side
)

response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello"}],
)
```

## Streaming

Strata supports Server-Sent Events streaming. Set `"stream": true` in your request to receive SSE chunks forwarded from the upstream LLM:

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4","messages":[{"role":"user","content":"Hi"}],"stream":true}'
```

## Configuration

All configuration is via environment variables (validated at startup with pydantic-settings):

| Variable | Default | Description |
|----------|---------|-------------|
| `STRATA_PORT` | `8000` | Proxy listen port |
| `STRATA_HOST` | `0.0.0.0` | Proxy bind address |
| `STRATA_CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `STRATA_DEFAULT_UPSTREAM` | `https://api.openai.com/v1` | Default upstream LLM base URL |
| `STRATA_UPSTREAM_API_KEY` | — | **Required.** Upstream API key |
| `STRATA_TIMEOUT` | `30` | Upstream request timeout (seconds) |
| `STRATA_MAX_CONCURRENT` | `100` | HTTPX connection pool size |
| `STRATA_LOG_LEVEL` | `INFO` | Logging level |
| `STRATA_DB_PATH` | `./data/strata.db` | SQLite database file path |
| `STRATA_MAX_TOKENS_PER_SESSION` | `50000` | Circuit breaker token limit per session |

Copy `.env.example` to `.env` and fill in your API key:

```bash
cp .env.example .env
```

## Telemetry

Every proxied request is logged to SQLite with the following data:

- `request_id` — unique UUID per request
- `timestamp` — ISO 8601
- `agent_id`, `session_id` — optional agent/session tracking
- `model` — requested model
- `tokens_in`, `tokens_out` — token usage from upstream
- `latency_ms` — total proxy latency
- `status_code` — upstream response code
- `upstream_url` — upstream base URL
- `redacted_tokens` — number of PII tokens redacted (Phase 2)
- `sub_status` — sub-status code (e.g., `injection_blocked`, `circuit_open`) (Phase 2)

Query the telemetry database directly:

```bash
sqlite3 ./data/strata.db "SELECT * FROM telemetry ORDER BY timestamp DESC LIMIT 10;"
```

## Project Structure

```
strata-gateway/
├── pyproject.toml
├── .env.example
└── strata/
    ├── main.py              # FastAPI app, lifespan, routes, streaming PII scrubber
    ├── config.py            # pydantic-settings configuration
    ├── core/
    │   └── proxy.py         # Proxy endpoint + streaming logic
    ├── middleware/
    │   ├── injection_guard.py   # Prompt injection detection (keyword matching)
    │   ├── pii_scrubber.py      # PII scrubbing (NHS, postcodes, MR/MS)
    │   └── circuit_breaker.py   # Per-session token tracking, 429 blocker
    ├── models/
    │   └── schemas.py       # Pydantic request/response models
    ├── db/
    │   ├── engine.py        # aiosqlite connection
    │   └── tables.py        # Database schema
    ├── telemetry/
    │   └── logger.py        # Telemetry writer
    └── tests/
        ├── conftest.py      # Shared fixtures
        ├── test_pii.py      # PII scrubber tests
        ├── test_injection.py # Injection guard tests
        ├── test_circuit.py  # Circuit breaker tests
        └── test_proxy.py    # Proxy integration tests
```

## Development

```bash
# Install with dev dependencies
uv sync --extra dev

# Run tests (all 23 pass)
uv run pytest strata/tests/ -v

# Run with auto-reload
uv run uvicorn strata.main:app --reload
```

## Roadmap

- **Phase 1** — Core proxy engine with streaming, telemetry, health checks ✅
- **Phase 2** — Security layer: PII scrubbing, injection guard, circuit breaker ✅
- **Phase 3** — Compliance: credential injection, DUAA audit logging
- **Phase 4** — Dashboard: React SPA with live feed, audit trail, video recording

## License

MIT
