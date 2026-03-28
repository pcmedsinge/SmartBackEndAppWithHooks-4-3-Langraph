# ClinAgent — Demo Run Guide

## Prerequisites

- Docker Desktop running
- Python 3.12+ with dependencies installed (`pip install -r requirements.txt`)
- OpenAI API key set in `clinagent/.env`

---

## Start

**1. Start HAPI FHIR** (if not already running)
```bash
docker run -d --name hapi-fhir -p 8082:8080 hapiproject/hapi:latest
```

**2. Start ClinAgent backend**
```bash
cd clinagent
uvicorn app.main:app --reload --port 8001
```

**3. Open sandbox:** https://sandbox.cds-hooks.org
- Settings → FHIR Server: `http://localhost:8082/fhir`
- Settings → CDS Service: `http://localhost:8001/cds-services`

**4. Select a patient:** Robbi844 · Ramon749 · Karena692

---

## Demo Scenarios

### Sepsis Detection
- Tab: **Patient View**
- Expected: 🔴 HIGH RISK card — qSOFA 3/3 (RR=24, SBP=92, GCS=13)
- Click **"Open Sepsis Checklist"** to launch the SMART app

### Drug–Drug Interaction
- Tab: **Rx Sign** (same patient — has active Warfarin + Simvastatin)
- Order **Aspirin** → ⚠️ WARNING — bleeding risk
- Order **Clarithromycin** → 🚫 CONTRAINDICATED — rhabdomyolysis

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Discovery endpoint fails | Check uvicorn is running: http://localhost:8001/cds-services |
| No patients in dropdown | Check HAPI FHIR is running: http://localhost:8082/fhir/metadata |
| Empty cards / no AI reasoning | Check `OPENAI_API_KEY` in `.env` |
| Two identical cards | Duplicate service URL in sandbox settings — remove one |
| Port 8001 blocked | Use `--port 8002` and update sandbox URL |
