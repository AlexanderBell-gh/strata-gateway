# NIST AI Risk Management Framework (AI RMF) Alignment

This document maps Strata's compliance controls to the four functions of **NIST AI RMF 1.0**: **Govern**, **Map**, **Measure**, and **Manage**.

---

## Overview

Strata is designed as an external semantic firewall for agentic AI systems. Its architecture aligns with NIST AI RMF by providing technical, programmatic enforcement of security and governance policies—rather than relying solely on system prompts or network-level controls. This mapping shows how each sub-function is satisfied by specific components in the Strata codebase.

> **Note:** This documentation lives alongside the implementation. All referenced components (e.g., `compliance/cred_injector.py`, middleware modules) are part of the repository under `strata-gateway/compliance/` and `strata-gateway/middleware/`.

---

## 1. Govern

### AI Governance Principles

| NIST Requirement | Strata Implementation | Location |
|------------------|----------------------|----------|
| **Accountability** — clear responsibility for AI system outcomes | Every request is logged with `agent_id`, `request_id`, and a human-review flag (DUAA HiTL). The audit log (`duaa_audit_log` table) provides immutable traceability. | `compliance/duaa_audit.py`, `db/tables.py` |
| **Fairness** — mitigate bias in automated decisions | High-risk outputs (e.g., legal judgments) trigger a human-in-the-loop hold, preventing unchecked automated decisions. | `middleware/duaa_gating.py` |
| **Transparency** — explainability of system behaviour | Full request/response payloads are recorded in telemetry; PII redaction events are logged. | `telemetry/logger.py`, `db/tables.py` |

### System Design & Architecture

- Strata operates as a **thick proxy**: it sits between the agent framework and the frontier model, inspecting and modifying traffic before forwarding. This avoids any reliance on the upstream LLM for security enforcement.
- **Zero-trust credential handling**: agents never receive real API keys; they use scoped temporary tokens issued by Strata. This satisfies NIST's requirement that security not be delegated to the model itself.

---

## 2. Map

### AI System Inventory

NIST expects organisations to maintain an inventory of their AI systems, including data flows and dependencies. Strata automatically generates this via its telemetry pipeline:

- Every incoming request (including metadata like `agent_id`, `model`, `prompt_template`) is logged in the `telemetry` table.
- The `agent_credentials` table tracks which credentials are associated with each agent, enabling auditors to reconstruct the full chain of trust.

### Data Lineage & PII Sensitivity

Strata's PII scrubber (Phase 2) records redaction events in the telemetry stream, providing a lineage view: original payload → detected sensitive fields → redacted output. This satisfies the "Map" requirement for understanding where personally identifiable information appears and how it is handled.

---

## 3. Measure

### Performance Metrics

NIST AI RMF recommends measuring key performance indicators such as accuracy, reliability, and safety. Strata's metrics are enforced at runtime:

| Metric | How Enforced |
|--------|--------------|
| **Token spend limits** (prevent runaway loops) | Circuit Breaker middleware (`middleware/circuit_breaker.py`) terminates the stream when a configurable token cap is exceeded, returning HTTP 403. |
| **Latency budgets** | Not strictly enforced in Phase 1, but the proxy design ensures predictable round-trip times by avoiding synchronous blocking; can be instrumented via OpenTelemetry if needed. |
| **Error rates** | Logged as part of telemetry; high error rates trigger alerts in the admin dashboard (Phase 4). |

### Risk Assessment

Strata performs continuous risk assessment through its middlewares:

- **Injection Guard** (`middleware/injection_guard.py`) detects prompt injection attempts and blocks them.
- **Circuit Breaker** mitigates infinite recursion risks.
- **DUAA Gating** flags outputs that could have legal/financial impact, effectively measuring "high-stakes" risk.

All these are recorded in the audit log, enabling post-hoc analysis.

---

## 4. Manage

### Mitigation Controls

| Control | Description | Location |
|--------|-------------|----------|
| **Kill-switch** | Immediate termination of a request (HTTP 403) when spending or iteration limits are breached. | `middleware/circuit_breaker.py` |
| **Credential exchange** | Scoped temporary tokens replace real API keys; Strata holds the service-account secrets and never passes them to agents. | `compliance/cred_injector.py`, `db/tables.py` |
| **Human-in-the-loop (HiTL)** | High-risk decisions are held pending human review before being returned to the client. | `compliance/duaa_audit.py`, `middleware/duaa_gating.py` |

### Ongoing Monitoring

Strata provides a live monitoring interface (Phase 4 dashboard) that displays:

- Real-time request feed
- PII redaction events
- Kill-switch triggers
- DUAA hold statuses

This satisfies NIST's expectation for continuous oversight and the ability to intervene when anomalies are detected.

---

## Implementation Checklist

When integrating Strata into a production environment, ensure the following controls are verified:

- [ ] All requests pass through the middleware pipeline in the documented order (CORS → Injection Guard → PII Scrubber → Circuit Breaker → DUAA Gating → Credential Injector).
- [ ] `agent_credentials` table is populated on startup with the service-account fallback.
- [ ] The telemetry schema includes `cred_event_type` and `duaa_audit` columns.
- [ ] Exportable audit logs (JSON Lines) can be streamed to an external SIEM.

---

## References

- NIST AI Risk Management Framework, Version 1.0: https://www.nist.gov/ai-risk-management-framework
