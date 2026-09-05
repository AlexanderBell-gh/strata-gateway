# Strata Gateway — Agent Guide

## Session Start
> **Rule**: Activate the `/caveman` Skill at `full` intensity

## Tech Stack

| Layer | Stack |
|-------|-------|
| Framework | FastAPI (Python 3.12+) |
| Language | Python, type hints throughout |
| Package mgr | uv (pyproject.toml, uv.lock) |
| Build | `hatchling` backend |
| HTTP client | httpx (async, upstream proxy) |
| DB | aiosqlite (SQLite, single-file) |
| Config | pydantic-settings (env vars, `.env` file) |
| Testing | pytest + pytest-asyncio |
| Runtime | uvicorn |

## Commands

```bash
uv run uvicorn strata.main:app --reload     # dev server
uv run pytest strata/tests/ -v              # run all tests
uv run pytest strata/tests/ -v -x           # stop on first failure
```

**No lint or typecheck commands exist.** There are no ruff, mypy, or flake8 configs.

## Verify before committing

Run the test suite:

```bash
uv run pytest strata/tests/ -v
```

All 23 tests should pass.

## Repository structure

```
strata/
  main.py                  FastAPI app, middleware registration, route handlers
  config.py                pydantic-settings Settings class (env vars)
  core/
    proxy.py               proxy_request (non-streaming), proxy_stream (streaming), list_models
  middleware/
    injection_guard.py     Prompt injection detection (keyword matching), 403 blocker
    pii_scrubber.py        PII scrubbing (NHS number, UK postcodes, MR/MS), ASGI send interception
    circuit_breaker.py     Per-session token tracking, 429 blocker when limit exceeded
  models/
    schemas.py             Pydantic models: ProxyRequest, TelemetryEvent
  db/
    engine.py              aiosqlite connection lifecycle
    tables.py              Telemetry table (redacted_tokens, sub_status columns)
  telemetry/
    logger.py              log_telemetry — async DB writer
  tests/
    conftest.py            Shared fixtures (client, env vars)
    test_pii.py            PII scrubber unit + integration tests
    test_injection.py      Injection guard integration tests
    test_circuit.py        Circuit breaker integration tests
    test_proxy.py          Proxy integration tests (non-streaming, streaming, concurrency)
```

- Entry: `strata/main.py` — FastAPI app with lifespan, middleware stack, 3 routes (`/health`, `/v1/chat/completions`, `/v1/models`)
- Middleware order is **immutable** per RULES.md §1: CORS → InjectionGuard → PIIScrubber → CircuitBreaker → Proxy
- Config: `strata/config.py` — `Settings` singleton, all values from env vars or `.env`

## Key gotchas

- **Middleware order is immutable.** CORS → InjectionGuard → PIIScrubber → CircuitBreaker → Proxy. Starlette `add_middleware` **prepends**, so registration order must be reversed: `CircuitBreaker`, `PIIScrubber`, `InjectionGuard`.
- **`STRATA_UPSTREAM_API_KEY` is required.** Settings validation raises `ValueError` on import if missing. Set in env or `.env` before any import.
- **Streaming PII scrubbing** is in `main.py` (`_stream_with_pii_scrub`), not in the middleware. The middleware is transparent for streaming requests (passes through). The endpoint wraps `proxy_stream` with the scrubber.
- **Circuit breaker detects streaming** via `content-type: text/event-stream` header. Streaming chunks are forwarded directly (no accumulation/token tracking). Non-streaming chunks are accumulated and parsed for usage.
- **Test env vars must be set before imports.** `conftest.py` sets `STRATA_UPSTREAM_API_KEY` at module level. Circuit breaker tests use `monkeypatch.setattr` to override `STRATA_MAX_TOKENS_PER_SESSION` because the `Settings` singleton is created at import time.
- **Circuit breaker tests patch `log_telemetry`** at `strata.middleware.circuit_breaker.log_telemetry`, not just `strata.core.proxy.log_telemetry`. The circuit breaker imports `log_telemetry` directly from `strata.telemetry.logger`.
- **Streaming proxy test was fixed** by setting `scope["asgi"]["spec_version"] = "2.4"` in each middleware. This prevents Starlette `StreamingResponse` from calling `listen_for_disconnect(receive)` which hung when `receive` was replaced with `receive_cached`. See PHASE2-FIXES.md Issue 4.
- **Database is not initialized in tests.** Tests that trigger `log_telemetry` must mock it to avoid `RuntimeError: Database not initialised`.

## Discovering recent changes

Use git to see what changed recently rather than reading file lists:

```bash
git log -n 5 --stat           # last 5 commits with file stats
git status                    # uncommitted changes
git diff                      # unstaged changes
git diff --cached             # staged changes
```

## External Documentation

- Phase specs: `/home/wsl/Projects/markdowns/strata-markdowns/planning/`
- Rules & guardrails: `/home/wsl/Projects/markdowns/strata-markdowns/planning/RULES.md`
- Phase 2 fixes: `/home/wsl/Projects/markdowns/strata-markdowns/planning/PHASE2-FIXES.md`

## Session Lifecycle Rules

### Multi-Doc Conclusion Protocol
Whenever the user says **"lets finish up and update the docs"**, you MUST perform the following documentation updates before stopping:

1. **Update MEMORY.md:**
   * Insert a reverse-chronological entry directly under the `## Session History` header.
   * Location: `/home/wsl/Projects/markdowns/strata-markdowns/MEMORY.md`
   
 ### **Format:**
     ### 📝 [DD-MM-YYYY] @ [GMT HH:MM 24-hr] | [Short Session Title]
     * **Changes:** [One-sentence summary of what was accomplished].
     * **Impacted Files:** `[file_1.ext]`, `[file_2.ext]`.
     * **Left Off At:** [One-sentence summary of outstanding next steps].

2. **Update CONTEXT.md:**
   * Review the current architectural state, tech stack details, or data flows.
   * Update any outdated sections to reflect the exact state of the codebase at the end of this session.
   * Location: `/home/wsl/Projects/markdowns/strata-markdowns/CONTEXT.md`

3. **Update README.md:**
   * Review `README.md`. If the session introduced new features, configuration keys (`.env`), or changed installation/build commands, update those specific sections. Do not alter stable project descriptions unless explicitly relevant.
   * Location: `/home/wsl/Projects/strata-gateway/README.md`

4. **Guard AGENTS.md (Strict Rule):**
   * **DO NOT** update `AGENTS.md` unless it is completely necessary. 
   * Updates to this file are strictly reserved for critical, sweeping architectural shifts, fundamental changes to the core tech stack, or major global project rules. Do not modify it for routine features, refactors, or bug fixes - this is to be kept very lean.
   * Location: `/home/wsl/Projects/strata-gateway/AGENTS.md`
