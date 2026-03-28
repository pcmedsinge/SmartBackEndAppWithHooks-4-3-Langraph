# ClinAgent — Claude Code Context

This file is read by Claude Code at the start of every session.
Do not delete it. Update the "Current phase" section after each milestone.

---

## What this project is

ClinAgent is an open-source agentic Clinical Decision Support system:
- **CDS Hooks v2.0.1** (HL7 standard) — FastAPI service that EHRs call at clinical workflow points
- **LangGraph** — AI agent that reasons over patient data and decides what recommendations to return
- **SMART on FHIR backend app** — fetches FHIR R4 resources using the bearer token the EHR provides
- **LLM** — OpenAI GPT-4o (primary) for clinical reasoning inside the agent

The EHR fires a hook → FastAPI receives it → LangGraph agent fetches FHIR data + reasons → returns CDS cards to EHR.

---

## Tech stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| CDS endpoint | FastAPI + uvicorn |
| Agent framework | LangGraph |
| LLM orchestration | LangChain + langchain-openai |
| FHIR client | fhirclient (R4) |
| Schema validation | Pydantic v2 |
| Observability | LangSmith |
| Containers | Docker + Docker Compose |
| Deployment | Azure Container Apps |
| SMART frontend | React (Vite) |
| Dev sandbox | sandbox.cds-hooks.org + r4.smarthealthit.org |

---

## Project structure

```
clinagent/
├── app/
│   ├── main.py                  # FastAPI app — CDS Hooks endpoints
│   ├── models/
│   │   ├── hooks.py             # Pydantic — CDS hook request/response
│   │   └── cards.py             # Pydantic — CDS card schema
│   ├── agents/
│   │   ├── ddi/
│   │   │   ├── graph.py         # LangGraph graph — DDI use case
│   │   │   ├── nodes.py         # Node functions
│   │   │   └── tools.py         # LangChain tools
│   │   └── sepsis/
│   │       ├── graph.py         # LangGraph graph — Sepsis use case
│   │       ├── nodes.py
│   │       └── tools.py
│   └── fhir/
│       └── client.py            # SMART on FHIR backend app
├── smart-app/                   # React SMART frontend (sepsis checklist)
├── tests/
│   └── fixtures/                # Sample hook payloads, FHIR bundles
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── CLAUDE.md                    # This file
├── requirements.md              # Living requirements document
└── phase1-plan.md               # Current phase plan
```

---

## Environment variables

```bash
OPENAI_API_KEY=...
LANGCHAIN_TRACING_V2=true
LANGSMITH_API_KEY=...
LANGCHAIN_PROJECT=clinagent
FHIR_SERVER_URL=https://r4.smarthealthit.org
SANDBOX_MODE=true              # disables JWT validation in dev
```

---

## Non-negotiable rules — follow in every file

1. **PHI never reaches the LLM** — strip patient name, DOB, MRN in context_parser node before any LLM call. Agent works on coded clinical values only.
2. **Always return valid cards** — never let the CDS endpoint return a 500. Catch all exceptions in the fallback node and return `{"cards": []}`.
3. **500ms budget** — FHIR fetches use prefetch where available. Skip LLM entirely if no clinical signal (e.g. qSOFA = 0). Agent timeout = 3000ms.
4. **Pydantic validation on every card** — card output from LangGraph is always validated against the CDS card schema before returning to FastAPI.
5. **LangSmith tracing on** — `LANGCHAIN_TRACING_V2=true` in all environments.
6. **Sandbox mode** — `SANDBOX_MODE=true` disables JWT validation and uses open FHIR endpoint. Never commit real API keys.

---

## CDS Hooks basics (for context)

The EHR sends a POST to `/cds-services/{id}` with this shape:
```json
{
  "hookInstance": "uuid",
  "hook": "order-sign",
  "context": {
    "patientId": "SMART-1288992",
    "userId": "Practitioner/SMART-Practitioner-1",
    "draftOrders": { "resourceType": "Bundle", "entry": [...] }
  },
  "fhirServer": "https://r4.smarthealthit.org",
  "fhirAuthorization": {
    "access_token": "...",
    "token_type": "Bearer",
    "scope": "patient/MedicationRequest.read"
  },
  "prefetch": {
    "medications": { "resourceType": "Bundle", "entry": [...] }
  }
}
```

The service responds with:
```json
{
  "cards": [
    {
      "summary": "Potential drug interaction detected",
      "indicator": "warning",
      "detail": "Agent reasoning: ...",
      "source": { "label": "ClinAgent", "url": "https://clinagent.example.com" },
      "suggestions": [...],
      "links": [...]
    }
  ]
}
```

---

## Current phase and milestone

**Phase:** 2
**Current milestone:** M1 — JWT validation middleware
**Status:** Not started
**Backend:** https://clinagent-api.onrender.com
**Frontend:** https://lemon-bush-011912610.1.azurestaticapps.net

---

## Phase 1 — Complete ✓

All 6 milestones delivered (2026-03-29):
- [x] M1: FastAPI skeleton + Pydantic models
- [x] M2: FHIR client (prefetch-first, live fallback, DSTU2 _sort graceful retry)
- [x] M3: DDI LangGraph agent (curated 18-pair dataset, GPT-4o reasoning)
- [x] M4: Sepsis LangGraph agent (qSOFA, LOINC extraction, SMART app link)
- [x] M5: React SMART app (qSOFA checklist, provider action tabs, dual launch mode)
- [x] M6: Docker + Render backend + Azure Static Web Apps frontend

---

## Phase 2 — Production Hardening

**Goal:** Make ClinAgent safe and ready for real EHR integration.
**Theme:** Security + Quality + Clinical Expansion

### M1 — JWT Validation Middleware
- FastAPI middleware that verifies EHR-issued JWT on every hook POST
- Validate: `iss`, `aud`, `exp`, `scope` claims
- Fetch EHR's public JWKS from well-known URL for signature verification
- `SANDBOX_MODE=true` bypasses validation (dev only)
- Files: `app/middleware/jwt_auth.py`, update `app/main.py`

### M2 — CDS Hooks Request Signing (JWK)
- Verify the `Authorization` header on hook requests using the EHR's JWK
- Implement per CDS Hooks v2.0.1 security spec
- Files: `app/middleware/hook_signing.py`

### M3 — Test Suite
- Unit tests for all tool functions (qSOFA scoring, DDI lookup, FHIR extraction)
- Integration tests: mock hook payloads against live agent graphs
- Fixture bundles for DSTU2 + R4 FHIR responses
- Files: `tests/test_sepsis_tools.py`, `tests/test_ddi_tools.py`, `tests/test_agents.py`

### M4 — Third Clinical Use Case: AKI (Acute Kidney Injury)
- Hook: `patient-view` (alongside sepsis — same hook, new service)
- Signal: Creatinine rise > 0.3 mg/dL within 48h OR > 1.5x baseline (KDIGO criteria)
- LOINC: Creatinine = 2160-0, eGFR = 62238-1
- Card: warning or critical based on AKI stage (1/2/3)
- Files: `app/agents/aki/`

### M5 — LangSmith Observability Setup
- Configure LangSmith project + API key
- Add per-agent run metadata: hook type, patient pseudoID, qSOFA score
- Latency dashboard: target p95 < 2000ms end-to-end
- Files: update all `nodes.py`, `.env.example`

### M6 — Rate Limiting + Abuse Protection
- Per-IP rate limiting on CDS endpoints (slowapi)
- Request size limit (reject oversized payloads)
- Structured error responses (never leak stack traces)
- Files: `app/middleware/rate_limit.py`

---

## How to update this file

After each milestone is complete, update the "Current milestone" line and check off the boxes.
After each phase is complete, update "Current phase" and replace the milestone section with the next phase plan.
This file is the single source of truth Claude Code uses to understand where the project is.
