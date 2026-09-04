# Stakeholder Analysis

This document identifies the key stakeholders affected by Strata's deployment and outlines their interests, expectations, and any relevant regulatory obligations.

---

## Primary Stakeholders

| Stakeholder | Relationship to Strata | Key Interests | Regulatory Context |
|-------------|------------------------|---------------|--------------------|
| **UK National Cyber Security Centre (NCSC)** | Procurement partner for the Sovereign AI R&D Scheme | Security of agentic systems, resilience testing, zero-trust controls | NCSC Cyber Essentials, ISO 27001 alignment |
| **Information Commissioner's Office (ICO)** | Data protection regulator | Enforcement of UK GDPR, DUAA compliance for automated decisions | UK GDPR, Data Use and Access Act |
| **Government departments using AI agents** | End users of Strata | Reliable, auditable decision-making; no data leaks to third-party models | Public sector AI policy (under development) |
| **Third-party model providers** (e.g., OpenAI, Anthropic) | Upstream API endpoints | Trustworthy traffic; no abuse of their services via compromised agents | Their own terms of service |

---

## Secondary Stakeholders

- **Developers integrating Strata** – need clear API documentation, SDKs, and examples.
- **Legal/compliance teams** – require audit logs and evidence of human-in-the-loop processes.
- **Incident response teams** – depend on telemetry for rapid detection of rogue agents or data exfiltration.

---

## Stakeholder Engagement Plan

Strata's design already embeds several stakeholder expectations:

- **Transparency:** All requests are logged; high-risk outputs are held pending human review.
- **Accountability:** Immutable audit trails (`duaa_audit_log`) enable post-hoc investigation.
- **Security-by-design:** Zero-trust credential handling and NCSC-aligned controls.

Further engagement (e.g., feedback loops with NCSC, quarterly compliance reviews) can be formalized in operational procedures as the project matures.
