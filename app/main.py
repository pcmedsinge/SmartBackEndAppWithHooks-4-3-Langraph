from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.agents.ddi.graph import run_ddi_agent
from app.agents.sepsis.graph import run_sepsis_agent
from app.models.cards import CDSResponse
from app.models.hooks import CDSRequest, CDSService, CDSServiceDiscovery

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ClinAgent", version="0.1.0")

# CDS Hooks spec requires the service to be accessible from EHR browser clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_SERVICES: list[CDSService] = [
    CDSService(
        hook="order-sign",
        title="ClinAgent — Drug-Drug Interaction Checker",
        description="Checks newly signed medication orders for clinically significant drug-drug interactions.",
        id="clinagent-ddi",
        prefetch={
            "medications": "MedicationRequest?patient={{context.patientId}}&status=active",
        },
    ),
    CDSService(
        hook="medication-prescribe",
        title="ClinAgent — Drug-Drug Interaction Checker",
        description="Checks newly signed medication orders for clinically significant drug-drug interactions.",
        id="clinagent-ddi-rx",
        prefetch={
            "medications": "MedicationRequest?patient={{context.patientId}}&status=active",
        },
    ),
    CDSService(
        hook="patient-view",
        title="ClinAgent — Sepsis Early Warning",
        description="Screens for early sepsis indicators using qSOFA and SIRS criteria.",
        id="clinagent-sepsis",
        prefetch={
            "conditions": "Condition?patient={{context.patientId}}&category=problem-list-item",
            "observations": "Observation?patient={{context.patientId}}&category=vital-signs&_sort=-date&_count=10",
        },
    ),
]


@app.get("/cds-services", response_model=CDSServiceDiscovery)
def discovery() -> CDSServiceDiscovery:
    """CDS Hooks discovery endpoint — returns the list of available services."""
    return CDSServiceDiscovery(services=_SERVICES)


@app.post("/cds-services/clinagent-ddi", response_model=CDSResponse)
async def clinagent_ddi(request: Request) -> CDSResponse:
    """DDI hook endpoint — runs the LangGraph DDI agent."""
    try:
        body = await request.json()
        hook_request = CDSRequest.model_validate(body)
        logger.info(
            "DDI hook received | hookInstance=%s patient=%s",
            hook_request.hookInstance,
            hook_request.context.get("patientId", "unknown"),
        )
        return await run_ddi_agent(body)
    except Exception as exc:
        logger.exception("Unhandled error in clinagent-ddi: %s", exc)
        return CDSResponse(cards=[])


@app.post("/cds-services/clinagent-ddi-rx", response_model=CDSResponse)
async def clinagent_ddi_rx(request: Request) -> CDSResponse:
    """DDI hook endpoint for medication-prescribe hook (sandbox compatibility)."""
    try:
        body = await request.json()
        return await run_ddi_agent(body)
    except Exception as exc:
        logger.exception("Unhandled error in clinagent-ddi-rx: %s", exc)
        return CDSResponse(cards=[])


@app.post("/cds-services/clinagent-sepsis", response_model=CDSResponse)
async def clinagent_sepsis(request: Request) -> CDSResponse:
    """Sepsis hook endpoint — runs the LangGraph Sepsis agent."""
    try:
        body = await request.json()
        hook_request = CDSRequest.model_validate(body)
        logger.info(
            "Sepsis hook received | hookInstance=%s patient=%s",
            hook_request.hookInstance,
            hook_request.context.get("patientId", "unknown"),
        )
        return await run_sepsis_agent(body)
    except Exception as exc:
        logger.exception("Unhandled error in clinagent-sepsis: %s", exc)
        return CDSResponse(cards=[])
