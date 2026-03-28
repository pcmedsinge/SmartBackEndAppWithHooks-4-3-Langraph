# ClinAgent — Phase 1 Plan

**Phase:** 1 — Foundation + Two Use Cases  
**Goal:** A working, publicly deployed, demo-ready ClinAgent that proves the full agentic CDS Hooks pipeline end-to-end  
**Outcome:** Anyone can hit the sandbox, register ClinAgent, trigger an order-sign or patient-view hook, and see an AI-generated CDS card with a visible reasoning trace in LangSmith

---

## What Phase 1 delivers

1. FastAPI CDS Hooks service (discovery + two hook endpoints)
2. LangGraph DDI agent (drug-drug interaction via `order-sign`)
3. LangGraph Sepsis agent (early warning via `patient-view`)
4. SMART on FHIR backend app (FHIR R4 fetcher, token passthrough)
5. Minimal SMART React app (sepsis checklist, launched via app-link card)
6. Docker Compose — full local stack in one command
7. Azure Container Apps deployment — public HTTPS endpoint
8. LangSmith tracing — every agent run observable

---

## Milestones

### M1 — Skeleton + CDS endpoint (start here)

**Goal:** A FastAPI service that passes the CDS Hooks discovery and responds to a hook with a hardcoded card. Proves the plumbing before any agent logic.

**Tasks:**
- [ ] Create project repo `clinagent` with structure from requirements.md
- [ ] `requirements.txt` — fastapi, uvicorn, langgraph, langchain, langchain-anthropic, fhirclient, pydantic
- [ ] `app/models/hooks.py` — Pydantic models for CDS hook request (hookInstance, hook, context, fhirServer, fhirAuthorization, prefetch)
- [ ] `app/models/cards.py` — Pydantic models for CDS card (summary, indicator, source, suggestions, links)
- [ ] `app/main.py` — FastAPI app with `GET /cds-services` and `POST /cds-services/{id}` returning a hardcoded card
- [ ] `.env.example` — all required env vars documented
- [ ] Test: register service in sandbox.cds-hooks.org, trigger hook, see hardcoded card appear

**Done when:** sandbox.cds-hooks.org shows the ClinAgent service and fires a hook that returns a card.

---

### M2 — SMART on FHIR backend app (FHIR fetcher)

**Goal:** A clean FHIR R4 client that fetches resources using the bearer token from the hook request.

**Tasks:**
- [ ] `app/fhir/client.py` — `FHIRClient` class wrapping `fhirclient`
  - `get_active_medications(patient_id, fhir_server, token)` → list of `MedicationRequest`
  - `get_observations(patient_id, category, fhir_server, token)` → list of `Observation`
  - `get_conditions(patient_id, fhir_server, token)` → list of `Condition`
  - `get_allergies(patient_id, fhir_server, token)` → list of `AllergyIntolerance`
- [ ] In `SANDBOX_MODE=true`: use open `r4.smarthealthit.org` — no token needed
- [ ] In prod mode: pass `Authorization: Bearer <token>` from `fhirAuthorization.access_token`
- [ ] Unit tests with sample FHIR R4 responses as fixtures in `tests/fixtures/`

**Done when:** `FHIRClient` fetches real patient data from `r4.smarthealthit.org` in a test.

---

### M3 — DDI LangGraph agent (UC-001)

**Goal:** A LangGraph graph that receives an order-sign hook, fetches medications, reasons about drug interactions, and returns a proper CDS card.

**Tasks:**
- [ ] `app/agents/ddi/tools.py`
  - `fetch_active_medications` — LangChain tool wrapping `FHIRClient`
  - `check_drug_interaction` — LangChain tool querying a drug interaction API or curated dataset (OpenFDA drug interactions or RxNorm API — both free)
- [ ] `app/agents/ddi/nodes.py` — implement each node function:
  - `context_parser` — extract patientId, draftOrders, fhirServer, token from hook state
  - `fhir_fetcher` — call `fetch_active_medications` tool
  - `llm_reasoner` — Claude/GPT-4o with system prompt instructing: reason over medications, call DDI tool, return structured output (interaction found: bool, severity: str, explanation: str, alternative: str)
  - `card_builder` — convert structured output to CDS card Pydantic model
  - `fallback` — return empty cards on any unhandled error
- [ ] `app/agents/ddi/graph.py` — wire nodes into LangGraph `StateGraph`:
  - Nodes: context_parser → fhir_fetcher → llm_reasoner → card_builder
  - Conditional edge: if llm_reasoner needs more data → back to fhir_fetcher
  - Error edge: any exception → fallback
- [ ] Wire `POST /cds-services/clinagent-ddi` in `main.py` to invoke the DDI graph
- [ ] LangSmith tracing enabled — set `LANGCHAIN_TRACING_V2=true`

**Done when:** order-sign hook in sandbox triggers DDI agent, returns a warning card with drug interaction explanation, trace visible in LangSmith.

---

### M4 — Sepsis LangGraph agent (UC-002)

**Goal:** A LangGraph graph that scores qSOFA criteria from live vitals observations and returns a sepsis risk card.

**Tasks:**
- [ ] `app/agents/sepsis/tools.py`
  - `fetch_vitals` — fetches recent Observation resources (respiratory rate, BP, GCS if available)
  - `fetch_labs` — fetches lactate, WBC Observations
  - `score_qsofa` — pure Python function scoring qSOFA (0-3): RR≥22 (+1), SBP≤100 (+1), altered mentation (+1)
- [ ] `app/agents/sepsis/nodes.py`
  - `context_parser` — extract patientId, fhirServer, token
  - `vitals_fetcher` — fetches vital signs observations
  - `lab_fetcher` — fetches lab observations (conditional — only if qSOFA ≥ 1)
  - `llm_reasoner` — receives qSOFA score + raw observations, reasons over clinical picture, produces risk assessment (risk_level: low/moderate/high, explanation: str, criteria_met: list)
  - `card_builder` — builds card; if risk_level=high → Critical card + app-link to SMART sepsis app; if moderate → Warning card; if low → no card
  - `fallback`
- [ ] `app/agents/sepsis/graph.py` — wire into StateGraph:
  - context_parser → vitals_fetcher → score_qsofa → conditional: if score≥1 → lab_fetcher → llm_reasoner → card_builder
  - if score=0 → return empty cards (skip LLM entirely — saves latency)
- [ ] Wire `POST /cds-services/clinagent-sepsis` in `main.py`

**Done when:** patient-view hook for a patient with abnormal vitals returns a sepsis warning card with qSOFA score and reasoning.

---

### M5 — SMART Sepsis Checklist App

**Goal:** A minimal React app that launches from the sepsis app-link card, pre-filled with the patient's vitals and qSOFA score.

**Tasks:**
- [ ] `smart-app/` — Create React app (Vite)
- [ ] SMART launch sequence — reads `launch` and `iss` params from URL, exchanges for token
- [ ] Fetches `Observation` resources using SMART token
- [ ] Displays: qSOFA score, criteria met/not met (RR, BP, mentation), Sepsis-3 checklist
- [ ] Read-only in Phase 1 — no write-back to EHR
- [ ] Register app in sandbox.cds-hooks.org as a SMART app
- [ ] Card app-link URL points to deployed smart-app

**Done when:** clicking the app-link card in the sandbox opens the checklist app pre-populated with patient vitals.

---

### M6 — Docker + Azure deployment

**Goal:** Full stack deployable locally in one command and publicly accessible on Azure for demos.

**Tasks:**
- [ ] `Dockerfile` — multi-stage build for FastAPI service
- [ ] `docker-compose.yml` — FastAPI service + env vars + optional local FHIR server
- [ ] Azure Container Apps deployment:
  - Container registry — Azure Container Registry or GitHub Container Registry
  - Deploy FastAPI service as Container App (HTTPS automatic)
  - Deploy SMART React app as Static Web App (free tier)
  - Set all env vars as Azure secrets
- [ ] `README.md`:
  - How to run locally with Docker Compose
  - How to register ClinAgent in sandbox.cds-hooks.org
  - How to trigger each use case with a test patient
  - Link to LangSmith public trace (if sharing)

**Done when:** `docker compose up` runs locally and Azure URL is live, reachable from sandbox.cds-hooks.org.

---

## What Phase 1 intentionally does NOT include

- JWT validation on inbound hook (production security — Phase 2)
- Multiple EHR targets (Epic, Oracle Health) — Phase 2+
- Persistent storage / database — not needed yet
- More than 2 use cases — quality over quantity
- Fine-tuned models — standard Claude/GPT-4o is sufficient
- FHIR write-back — read-only in Phase 1

---

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| LLM response exceeds 500ms budget | Score qSOFA without LLM first; only invoke LLM if score ≥ 1. DDI tool lookup is fast — LLM only explains, doesn't discover |
| Sandbox FHIR patients lack vital signs | Use Synthea-generated patients from r4.smarthealthit.org — they have full vital sign histories |
| LLM hallucinates drug interaction | Card builder validates output schema strictly. Card only fires if DDI tool confirms interaction — LLM provides explanation only |
| Azure cold start latency | Use always-on min replica = 1 in Container Apps config |

---

## Order to build

```
M1 (skeleton) → M2 (FHIR client) → M3 (DDI agent) → M4 (Sepsis agent) → M5 (SMART app) → M6 (deploy)
```

Build in this order. M1 and M2 together take one session. M3 is the longest milestone — plan 2-3 sessions. Each milestone produces something runnable — never more than one milestone of broken code at a time.

---

## How Phase 2 will be decided

At the end of Phase 1, we review:
- Which agent node is the latency bottleneck?
- Did the LLM reasoning add real value over a rule engine for DDI?
- What FHIR resources were missing or unreliable in the sandbox?
- What did demo audiences respond to most?

Phase 2 scope emerges from those answers. Candidates: add UC-003 (readmission risk), add JWT validation, add a second SMART app, or deepen the LangGraph graph with memory/persistence.
