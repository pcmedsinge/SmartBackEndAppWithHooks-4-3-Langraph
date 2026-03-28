# ClinAgent

An open-source agentic Clinical Decision Support (CDS) system built with CDS Hooks v2.0.1, LangGraph, and GPT-4o.

**Backend:** https://clinagent-api.onrender.com
**Frontend:** https://lemon-bush-011912610.1.azurestaticapps.net

---

## What it does

The EHR fires a CDS Hook at a clinical workflow point → ClinAgent's LangGraph agent fetches FHIR data, reasons with GPT-4o, and returns actionable CDS cards back to the EHR.

Two clinical use cases:

| Hook | Use Case | Signal | Card |
|---|---|---|---|
| `patient-view` | Sepsis Early Warning | qSOFA score (RR, SBP, GCS) | 🔴 HIGH RISK / 🟡 MODERATE |
| `order-sign` | Drug–Drug Interaction | RxCUI pair lookup (FDA black-box) | ⚠️ WARNING / 🚫 CONTRAINDICATED |

---

## Architecture

```
EHR / Sandbox
    │  POST /cds-services/{id}
    ▼
FastAPI  ──────────────────────────────────────────────────────►  CDS Cards
    │                                                                  │
    ▼                                                          clinician clicks
LangGraph StateGraph                                                   │
  context_parser                                                       ▼
  fhir_fetcher  ◄──► HAPI FHIR R4                          React SMART App (Azure)
  checker/scorer                                             qSOFA checklist
  llm_reasoner  ◄──► GPT-4o (PHI-free input only)          Provider action tabs
  card_builder
```

PHI is stripped in `context_parser` before any data reaches GPT-4o. Only LOINC codes, RxCUI codes, and numeric values are sent to the LLM.

---

## Quick start

**Prerequisites:** Docker, Python 3.12+, OpenAI API key

```bash
# 1. Start local HAPI FHIR
docker run -d --name hapi-fhir -p 8082:8080 hapiproject/hapi:latest

# 2. Clone and install
git clone https://github.com/pcmedsinge/SmartBackEndAppWithHooks-4-3-Langraph.git
cd SmartBackEndAppWithHooks-4-3-Langraph/clinagent
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Edit .env — set OPENAI_API_KEY

# 4. Seed demo patients
python tests/seed_fhir.py reseed

# 5. Run
uvicorn app.main:app --reload --port 8001
```

Register in [sandbox.cds-hooks.org](https://sandbox.cds-hooks.org):
- FHIR Server: `http://localhost:8082/fhir`
- CDS Service: `http://localhost:8001/cds-services`

See `docs/demo-instructions.md` for full demo scenarios.

---

## Tech stack

| Layer | Technology |
|---|---|
| CDS endpoint | FastAPI + uvicorn |
| Agent framework | LangGraph |
| LLM | GPT-4o via langchain-openai |
| FHIR | HAPI FHIR R4 (local) |
| Schema validation | Pydantic v2 |
| Frontend | React + Vite (SMART on FHIR) |
| Backend hosting | Render |
| Frontend hosting | Azure Static Web Apps |

---

## Project structure

```
clinagent/
├── app/
│   ├── main.py                  # FastAPI — CDS Hooks endpoints
│   ├── models/                  # Pydantic schemas (hooks, cards)
│   ├── agents/
│   │   ├── ddi/                 # DDI LangGraph agent
│   │   └── sepsis/              # Sepsis LangGraph agent
│   └── fhir/client.py           # SMART on FHIR FHIR client
├── smart-app/                   # React SMART frontend
├── tests/seed_fhir.py           # Demo patient seeding
└── docs/                        # workflow.svg · handshake.svg · demo-instructions.md
```

---

## Docs

- [`docs/workflow.svg`](docs/workflow.svg) — Complete system workflow diagram
- [`docs/handshake.svg`](docs/handshake.svg) — Demo vs production security comparison
- [`docs/demo-instructions.md`](docs/demo-instructions.md) — Demo run guide

---

## License

MIT
