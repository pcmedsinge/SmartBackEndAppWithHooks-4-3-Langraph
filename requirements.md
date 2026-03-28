# ClinAgent — Requirements Document

**Project:** ClinAgent — Agentic Clinical Decision Support with SMART on FHIR  
**Version:** 2.0 (final pre-build)  
**Date:** 2026-03-27  
**Status:** Approved — Phase 1 ready  
**Approach:** Phase-by-phase evolution. This document is a living north star, not a frozen spec.

---

## 1. Vision

ClinAgent is an open-source, production-quality Clinical Decision Support system that combines:

- **HL7 CDS Hooks v2.0.1** — the integration standard that makes CDS services pluggable into any EHR
- **SMART on FHIR backend app** — fetches live patient data from FHIR R4 servers using the token the EHR provides
- **LangGraph agentic workflow** — an AI agent that autonomously reasons over FHIR data, calls tools, and decides what clinical recommendations to return
- **LLM (Claude / GPT-4o)** — the reasoning engine inside the agent

The goal is to demonstrate that agentic AI can deliver genuinely intelligent, explainable, production-safe clinical decision support — not just rule-based alerts — through open interoperability standards.

---

## 2. Core Principles (apply to all phases)

| Principle | What it means in practice |
|---|---|
| **Standards-first** | CDS Hooks v2.0.1, FHIR R4, SMART on FHIR — no vendor lock-in |
| **Agent, not rules** | LangGraph + LLM reasons over data — no hardcoded if/else clinical logic |
| **Explainability** | Every card detail field shows the agent's reasoning in plain English |
| **Production-safe** | Pydantic schema validation, graceful degradation, 500ms discipline, no PHI in LLM prompts |
| **Observable** | LangSmith traces every agent graph run — every node, tool call, and LLM prompt visible |
| **Phase-by-phase** | Each phase delivers a working, demo-ready increment. No big-bang releases. |

---

## 3. Architecture (stable across all phases)

### 3.1 System Components

```
┌─────────────────────────────────────────────────────────┐
│                    EHR / CDS Client                      │
│           (sandbox.cds-hooks.org in dev)                │
└────────────────────────┬────────────────────────────────┘
                         │ hook fires (order-sign / patient-view)
                         │ POST /cds-services/{id}
                         ▼
┌─────────────────────────────────────────────────────────┐
│              FastAPI — CDS Hooks Gateway                 │
│   /cds-services  /cds-services/{id}  (Python 3.12)      │
│   Validates request → hands off to LangGraph            │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│              LangGraph Agent Workflow                    │
│                                                         │
│  [Context Parser] → [FHIR Fetcher] → [LLM Reasoner]   │
│        ↑                                    │           │
│        └──── conditional re-fetch ←────────┘           │
│                                    ↓                   │
│                           [Card Builder]                │
└────────────────────────┬────────────────────────────────┘
                         │ bearer token passthrough
                         ▼
┌─────────────────────────────────────────────────────────┐
│         SMART on FHIR Backend App (fhirclient)          │
│    Fetches FHIR R4 resources using token from hook      │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│              FHIR R4 Server                             │
│   r4.smarthealthit.org (dev) / EHR FHIR API (prod)     │
└─────────────────────────────────────────────────────────┘
```

### 3.2 LangGraph Agent Graph (per use case)

Each use case is a separate LangGraph graph with these standard node types:

| Node | Role |
|---|---|
| `context_parser` | Parses hook payload into typed state (patientId, hook, fhirServer, token, draftOrders) |
| `fhir_fetcher` | Tool node — fetches FHIR resources via SMART backend app using bearer token |
| `llm_reasoner` | LLM node — reasons over FHIR data, calls domain tools, produces structured recommendation |
| `card_builder` | Converts agent output to CDS Hooks v2.0.1 card schema, validates with Pydantic |
| `fallback` | Returns empty cards safely if agent times out or fails |

Edges between nodes are conditional — the agent can loop back to `fhir_fetcher` if it needs more data before reasoning.

### 3.3 Technology Stack (locked)

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| CDS endpoint | FastAPI |
| Agent framework | LangGraph |
| LLM orchestration | LangChain (tools, RAG, prompt templates) |
| LLM model | Claude 3.5 Sonnet (primary) / GPT-4o (fallback) |
| FHIR client | `fhirclient` (Python) — FHIR R4 |
| Schema validation | Pydantic v2 |
| Observability | LangSmith (agent traces) |
| Containerisation | Docker + Docker Compose |
| Deployment | Azure Container Apps (HTTPS, public endpoint) |
| Dev sandbox | sandbox.cds-hooks.org + r4.smarthealthit.org |
| SMART frontend | React (minimal, for app-link cards) |

---

## 4. Security Model (stable across all phases)

### 4.1 The three auth legs — always

| Leg | Sandbox | Production |
|---|---|---|
| EHR → CDS service (inbound JWT) | Accept without validation | Validate JWT via EHR JWKS endpoint |
| SMART backend → FHIR server (outbound) | Open endpoint — no token needed | Use `access_token` from `fhirAuthorization` in hook |
| CDS service → EHR (card response) | Plain HTTP response | Plain HTTP response |

### 4.2 PHI handling — non-negotiable in all phases

- Patient identifiers (name, DOB, MRN) are **never** sent to the LLM
- The agent works on clinical facts only: resource types, coded values, numeric results
- Example: agent receives `{"resourceType":"Observation","code":"8867-4","value":72}` — not `{"patient":"John Smith"}`
- All de-identification happens in `context_parser` before any LLM node

### 4.3 Environment variables — never hardcoded

```
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...          # fallback
LANGSMITH_API_KEY=...
FHIR_SERVER_URL=https://r4.smarthealthit.org
SANDBOX_MODE=true           # disables JWT validation in dev
```

---

## 5. CDS Hooks API Contract (stable across all phases)

### 5.1 Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/cds-services` | Discovery — returns all registered services |
| `POST` | `/cds-services/{service-id}` | Invoke a CDS service |
| `GET` | `/health` | Health check for deployment monitoring |

### 5.2 Non-functional requirements (apply to every phase)

| Requirement | Value |
|---|---|
| Max response time | 500ms (CDS Hooks spec) |
| Agent timeout | 3000ms — returns empty cards on timeout |
| FHIR calls | Use prefetch where available; fetch only what agent needs |
| Card schema | CDS Hooks v2.0.1 — validated by Pydantic before return |
| Empty cards | Always return `{"cards": []}` — never 500 to the EHR |
| Logging | Every hook request and card response logged with hookInstance ID |

---

## 6. Use Case Registry

This section grows with each phase. Each use case has a stable ID.

### UC-001: Drug-Drug Interaction Alert *(Phase 1)*

| Field | Value |
|---|---|
| Hook | `order-sign` |
| Service ID | `clinagent-ddi` |
| Card type | Warning / Critical + Suggestion |
| FHIR resources | `MedicationRequest`, `AllergyIntolerance`, `Patient` |
| Agent tools | FHIR fetcher, drug interaction database lookup, LLM reasoner |
| Prefetch | `MedicationRequest?patient={{context.patientId}}&status=active` |
| Earning story | Adverse drug events cost $3.5B/year US. Prevention = liability reduction + quality metric improvement |

**Agent behaviour:** Receives draft order → fetches active medications → calls DDI tool → LLM reasons over interaction severity → returns card with explanation and safe alternative suggestion.

---

### UC-002: Sepsis Early Warning *(Phase 1)*

| Field | Value |
|---|---|
| Hook | `patient-view` |
| Service ID | `clinagent-sepsis` |
| Card type | Warning / Critical + App-link (launches SMART sepsis checklist) |
| FHIR resources | `Observation` (vitals, lactate, WBC), `Condition`, `DiagnosticReport`, `Patient` |
| Agent tools | FHIR fetcher (multi-resource), qSOFA scorer, LLM reasoner |
| Prefetch | `Observation?patient={{context.patientId}}&category=vital-signs&_sort=-date&_count=10` |
| Earning story | Sepsis kills 250K/year US. AI detection 6hrs earlier. $1.5M–$3M annual savings per 100-bed hospital |

**Agent behaviour:** On chart open → fetches recent vitals + labs → scores qSOFA criteria (altered mentation, respiratory rate ≥22, systolic BP ≤100) → if threshold met, LLM reasons over full clinical picture → returns warning card + app-link to SMART sepsis workup checklist pre-filled with patient vitals.

**SMART app:** Minimal React app launched from the app-link card. Displays qSOFA score, met criteria, and Sepsis-3 checklist. Read-only in Phase 1.

---

*Additional use cases will be added here as phases progress. Candidates include:*
- *UC-003: 30-day readmission risk (encounter-discharge)*
- *UC-004: Imaging appropriateness / AUC (order-select)*
- *UC-005: Duplicate lab order detection (order-sign)*
- *UC-006: Medication reconciliation gap (patient-view)*

---

## 7. Project Structure (target)

```
clinagent/
├── app/
│   ├── main.py                  # FastAPI app, CDS endpoints
│   ├── models/
│   │   ├── hooks.py             # Pydantic models — CDS hook request/response
│   │   └── cards.py             # Pydantic models — CDS card schema
│   ├── agents/
│   │   ├── ddi/
│   │   │   ├── graph.py         # LangGraph graph definition — DDI use case
│   │   │   ├── nodes.py         # Node functions (context_parser, fhir_fetcher, etc.)
│   │   │   └── tools.py         # LangChain tools (DDI DB lookup, etc.)
│   │   └── sepsis/
│   │       ├── graph.py         # LangGraph graph definition — Sepsis use case
│   │       ├── nodes.py
│   │       └── tools.py         # qSOFA scorer, vitals fetcher
│   └── fhir/
│       └── client.py            # SMART on FHIR backend app — FHIR R4 client
├── smart-app/                   # React SMART frontend (sepsis checklist)
│   ├── src/
│   └── public/
├── tests/
│   ├── test_ddi.py
│   ├── test_sepsis.py
│   └── fixtures/                # Sample hook payloads, FHIR bundles
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── requirements.md              # This document
└── README.md
```

---

## 8. Definition of Done — per phase

Every phase must deliver all of these before it is considered complete:

- [ ] All use cases for the phase return valid CDS Hooks v2.0.1 cards in the sandbox
- [ ] LangSmith shows clean agent traces with no unhandled exceptions
- [ ] Empty cards returned gracefully on timeout or FHIR error
- [ ] PHI de-identification verified — no patient identifiers in LangSmith traces
- [ ] Docker Compose runs the full stack locally with one command
- [ ] Azure deployment is live at a public HTTPS URL
- [ ] README documents how to test each use case in the sandbox
- [ ] requirements.md updated with any architectural decisions made during the phase

---

## 9. What this document is NOT

- It is not a task list or sprint board — those live in the phase plan
- It is not frozen — it evolves as the project learns
- It is not a full design spec — implementation details are decided during each phase
- It does not plan beyond the current phase — future phases are directional only

---

## 10. Glossary

| Term | Definition |
|---|---|
| CDS Hooks | HL7 spec for plugging decision support into EHR workflows via REST hooks |
| CDS Client | The EHR that fires hooks and displays cards |
| CDS Service | The backend that receives hooks and returns cards (ClinAgent) |
| LangGraph | Python framework for building stateful, multi-node AI agent workflows as directed graphs |
| LangChain | Python library for LLM tool use, RAG, prompt templates — used inside LangGraph nodes |
| LangSmith | Observability platform for LangGraph/LangChain — traces every agent run |
| SMART on FHIR | Standard for secure app auth and FHIR data access |
| FHIR R4 | HL7 FHIR Release 4 — the resource format for clinical data |
| fhirAuthorization | Field in CDS hook request containing the pre-issued bearer token for FHIR access |
| prefetch | FHIR resources pre-loaded by the EHR in the hook request to avoid extra round trips |
| qSOFA | Quick Sequential Organ Failure Assessment — 3-criterion sepsis screening score |
| order-sign | Hook fired when a practitioner finalises a medication or lab order |
| patient-view | Hook fired when a patient chart is opened |
| PHI | Protected Health Information — patient identifiers, never sent to LLM |
| Card | Structured JSON returned by CDS service to display a recommendation in the EHR |
