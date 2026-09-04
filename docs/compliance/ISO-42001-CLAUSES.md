# ISO/IEC 42001:2023 (AI Management System) Alignment

This document maps Strata's architecture and controls to the clauses of **ISO/IEC 42001:2023**, the international standard for an AI management system (AIMS). The goal is to demonstrate that Strata can satisfy the requirements of a certified AIMS when deployed in regulated environments.

> **Scope note:** ISO 42001 applies to the *management system* that oversees AI systems, not to the raw model weights themselves. Strata's role as a governance proxy aligns well with this scope, as it enforces policies, monitors risk, and maintains auditability for all downstream agents.

---

## Clause-by-Clause Mapping

### 5. Context of the Organisation (Clause 4)

| Requirement | Strata Implementation |
|-------------|----------------------|
| **4.1** – Understand the organisation and its purpose | Scope defined in `config.py`: Strata is an "external semantic firewall" for autonomous AI agents interacting with frontier models. |
| **4.2** – Interested parties (stakeholders) | Stakeholder list (NCSC, ICO, government agencies, end-users) documented in `docs/compliance/stakeholders.md` (to be created). |
| **4.3** – External issues (regulatory landscape) | References to UK GDPR, DUAA, and NCSC guidance embedded throughout the compliance layer. |

### 5.1 Scope of the Management System (Clause 4.3)

Strata's AIMS covers all AI agents that pass through the proxy. The system boundary is:
- **Inbound:** any agent framework (LangChain, AutoGen, CrewAI, etc.) communicating via the `/v1/chat/completions` endpoint.
- **Outbound:** frontier model APIs (OpenAI, Anthropic) or downstream services.

Everything in between — the proxy, middlewares, credential store, audit logs — is within scope. Anything upstream of the proxy (e.g., the user's own application logic) is outside the AIMS but must comply with its outputs.

### 6. Leadership (Clause 5)

| Requirement | Strata Implementation |
|-------------|----------------------|
| **5.1** – Leadership commitment | The proxy enforces "accountability" via immutable audit logs and human-review gates — a form of institutionalised commitment. |
| **5.2** – AI policy | Policy is encoded in the middleware pipeline: injection guard, PII scrubber, circuit breaker, DUAA gating. These collectively constitute the organisation's AI risk management policy. |
| **5.3** – Roles and responsibilities | Role definitions (admin, agent, service account) are enforced by the credential injector; each role has distinct token scopes. |

### 6.1 AI Governance Principles (Clause 5.3)

Strata operationalises NIST's "Govern" principles:
- **Accountability** — every action is logged with `agent_id` and a unique `request_id`.
- **Transparency** — the telemetry stream and audit logs are exportable; PII redaction events are recorded.
- **Fairness** — high-stakes decisions trigger human review, mitigating unchecked automated bias.

### 7 Planning (Clause 6)

| Requirement | Strata Implementation |
|-------------|----------------------|
| **7.1** – AI risk assessment | Risk is assessed continuously: injection guard (prompt injection), circuit breaker (runaway loops), DUAA gating (legal/financial impact). |
| **7.2** – Risk treatment plan | Mitigation controls are implemented in the middleware stack; see Section 8 for details. |
| **7.3** – Objectives, planning, and resources | Objectives: secure adoption, auditability, compliance with UK law. Resources: PostgreSQL database, FastAPI server, React dashboard (Phase 4). |

### 8 Support (Clause 7)

| Requirement | Strata Implementation |
|-------------|----------------------|
| **7.1** – Competence and awareness | Agent frameworks using Strata must respect role-based scopes; documentation in `docs/usage.md` (to be written). |
| **7.2** – Awareness of policy | The injection guard and DUAA gating enforce policy at runtime; agents are aware implicitly via token rejection when violating rules. |
| **7.3** – Communication | Telemetry logs provide an internal communication channel between components. |

### 8.1 Documentation

All compliance documentation for ISO 42001 is stored under `docs/compliance/`. Additional usage and admin docs will be added as the project matures.

### 9 AI System Development, Operation, and Use (Clause 8)

| Requirement | Strata Implementation |
|-------------|----------------------|
| **9.1** – Lifecycle considerations | Strata sits at the runtime boundary; it does not modify model weights but enforces constraints on all lifecycle stages that pass through it. |
| **9.2** – Development controls | The middleware pipeline provides development-time checks (e.g., static analysis of prompts via injection guard). |
| **9.3** – Operational controls | Runtime enforcement: PII redaction, circuit breaker, credential exchange, human-in-the-loop holds. |
| **9.4** – Use and deployment | Deployed as a standalone API service; agents integrate by pointing their HTTP client at Strata's `/v1/chat/completions`. |

### 9.3 Operational Controls (Clause 8.3) — Detailed Mapping

| Control | Purpose | Strata Component |
|--------|---------|------------------|
| **PII redaction** | Prevent leakage of personal data to external models | `middleware/pii_scrubber.py` |
| **Injection guard** | Block prompt injection attempts | `middleware/injection_guard.py` |
| **Circuit breaker** | Stop runaway token consumption | `middleware/circuit_breaker.py` |
| **DUAA HiTL gate** | Enforce human review for high-risk outputs | `compliance/duaa_audit.py`, `middleware/duaa_gating.py` |
| **Credential injector** | Zero-trust access to downstream APIs | `compliance/cred_injector.py` |

These controls are applied in the documented order (see Phase 3 technical spec). They collectively satisfy ISO 42001's requirement for "appropriate operational controls" tailored to the risks identified in 9.1–9.2.

### 10 Evaluation of Results (Clause 9)

| Requirement | Strata Implementation |
|-------------|----------------------|
| **9.1** – Monitoring, measurement, analysis, evaluation | Telemetry pipeline records all events; the admin dashboard aggregates metrics for review. |
| **9.2** – Audit trail | The `duaa_audit_log` and `telemetry` tables constitute an immutable record of every request, redaction, and kill-switch event. |

### 10.1 Internal Audit Programme (Clause 9.2)

Strata is not itself an audit tool, but it produces the raw data required for audits. Periodic internal audits can query:
- `duaa_audit_log` for all high-risk decisions and their review status.
- `telemetry` for token spend patterns and injection-guard rejections.

---

## Implementation Notes

1. **Database schema** — All tables referenced above (`telemetry`, `agent_credentials`, `duaa_audit_log`) are defined in `strata-gateway/db/tables.py`. Ensure migrations are run before deployment.
2. **Middleware order** — The pipeline sequence is critical; see Phase 3's technical spec for the exact ordering.
3. **Exportable logs** — For SIEM integration, Strata can serve audit events as JSON Lines via a dedicated endpoint (e.g., `GET /api/v1/audit/export`). This is out of scope for the current MVP but should be considered in Phase 4.

---

## References

- ISO/IEC 42001:2023 — Information security, cybersecurity and privacy protection — Artificial intelligence — Management systems.
- NIST AI RMF 1.0 (see `docs/compliance/nist-ai-rmf.md`) — for cross-framework alignment.
