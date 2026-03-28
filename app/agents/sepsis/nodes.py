from __future__ import annotations

import logging
import os
from typing import Any

from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.agents.sepsis.tools import extract_labs, extract_vitals, score_qsofa
from app.fhir.client import FHIRClient, resolve
from app.models.cards import Card, CDSResponse, Indicator, Link, Source

logger = logging.getLogger(__name__)

_SOURCE = Source(label="ClinAgent — Sepsis Early Warning", url="https://github.com/clinagent")


# ---------------------------------------------------------------------------
# Structured LLM output
# ---------------------------------------------------------------------------

class SepsisReasonerOutput(BaseModel):
    risk_level: str          # "low" | "moderate" | "high"
    assessment: str          # clinical reasoning — NO patient identifiers
    key_findings: list[str]  # bullet points of abnormal values / concerns
    recommendation: str      # actionable next step for the clinician


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------

async def context_parser(state: dict[str, Any]) -> dict[str, Any]:
    req = state["hook_request"]
    context = req.get("context", {})

    patient_id = context.get("patientId", "")
    fhir_server = req.get("fhirServer") or os.getenv("FHIR_SERVER_URL", "https://r4.smarthealthit.org")
    token = None
    auth = req.get("fhirAuthorization")
    if auth:
        token = auth.get("access_token")

    logger.info("sepsis context_parser | patient=%s", patient_id)
    return {**state, "patient_id": patient_id, "fhir_server": fhir_server, "token": token}


async def vitals_fetcher(state: dict[str, Any]) -> dict[str, Any]:
    """Fetch recent vital sign observations (prefetch first, live fallback)."""
    client = FHIRClient(base_url=state["fhir_server"], token=state.get("token"))
    prefetch = state["hook_request"].get("prefetch")

    bundle = await resolve(
        prefetch,
        "observations",
        client,
        "Observation",
        state["patient_id"],
        extra_params={"category": "vital-signs", "_sort": "-date", "_count": "10"},
    )

    vitals = extract_vitals(bundle)
    qsofa = score_qsofa(vitals)
    logger.info(
        "sepsis vitals_fetcher | rr=%s sbp=%s gcs=%s qsofa=%d",
        vitals["respiratory_rate"],
        vitals["systolic_bp"],
        vitals["gcs_total"],
        qsofa["score"],
    )
    return {**state, "vitals": vitals, "qsofa": qsofa}


async def lab_fetcher(state: dict[str, Any]) -> dict[str, Any]:
    """Fetch lactate and WBC labs — only called when qSOFA >= 1."""
    client = FHIRClient(base_url=state["fhir_server"], token=state.get("token"))

    bundle = await resolve(
        None,  # labs rarely in prefetch — always live
        "labs",
        client,
        "Observation",
        state["patient_id"],
        extra_params={"category": "laboratory", "_sort": "-date", "_count": "20"},
    )

    labs = extract_labs(bundle)
    logger.info("sepsis lab_fetcher | lactate=%s wbc=%s", labs["lactate"], labs["wbc"])
    return {**state, "labs": labs}


async def llm_reasoner(state: dict[str, Any]) -> dict[str, Any]:
    """GPT-4o reasons over qSOFA score + vitals + labs. No PHI sent."""
    qsofa = state["qsofa"]
    vitals = qsofa["raw_vitals"]
    labs = state.get("labs", {})
    criteria = qsofa["criteria"]

    vitals_text = (
        f"- Respiratory rate: {vitals['respiratory_rate']} breaths/min\n"
        f"- Systolic BP: {vitals['systolic_bp']} mmHg\n"
        f"- GCS: {vitals['gcs_total']}"
    )
    labs_text = (
        f"- Lactate: {labs.get('lactate')} mmol/L\n"
        f"- WBC: {labs.get('wbc')} x10³/µL"
    )
    criteria_text = "\n".join(f"- {c}" for c in criteria) if criteria else "- None met"

    system_prompt = (
        "You are a clinical decision support assistant specializing in sepsis early warning. "
        "You receive coded vital sign and laboratory values (no patient identifiers). "
        "Assess the sepsis risk based on the qSOFA score and supporting data. "
        "Be concise and actionable. Do NOT include any patient identifiers in your response."
    )

    user_prompt = (
        f"qSOFA score: {qsofa['score']}/3\n"
        f"qSOFA criteria met:\n{criteria_text}\n\n"
        f"Vital signs:\n{vitals_text}\n\n"
        f"Recent labs:\n{labs_text}\n\n"
        "Provide a sepsis risk assessment and clinical recommendation."
    )

    try:
        llm = ChatOpenAI(model="gpt-4o", temperature=0).with_structured_output(SepsisReasonerOutput)
        output: SepsisReasonerOutput = await llm.ainvoke(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )
    except Exception as exc:
        logger.exception("sepsis llm_reasoner failed: %s", exc)
        score = qsofa["score"]
        risk = "high" if score >= 2 else "moderate"
        output = SepsisReasonerOutput(
            risk_level=risk,
            assessment=f"qSOFA score {score}/3 with {len(criteria)} criterion/criteria met. Manual review required.",
            key_findings=criteria,
            recommendation="Assess patient urgently for sepsis. Obtain blood cultures, lactate, and consider empiric antibiotics per institutional protocol.",
        )

    logger.info("sepsis llm_reasoner | risk_level=%s", output.risk_level)
    return {**state, "llm_output": output}


async def card_builder(state: dict[str, Any]) -> dict[str, Any]:
    """Build CDS card. high → critical, moderate → warning, low → no card."""
    output: SepsisReasonerOutput = state["llm_output"]
    qsofa = state["qsofa"]

    risk_level = output.risk_level.lower()

    if risk_level == "low":
        return {**state, "cards": []}

    indicator = Indicator.critical if risk_level == "high" else Indicator.warning
    findings_text = "\n".join(f"- {f}" for f in output.key_findings)

    detail = (
        f"**qSOFA Score: {qsofa['score']}/3**\n\n"
        f"**Key findings:**\n{findings_text}\n\n"
        f"**Assessment:** {output.assessment}\n\n"
        f"**Recommendation:** {output.recommendation}"
    )

    smart_app_url = os.getenv("SMART_APP_URL", "")
    links = []
    if smart_app_url:
        fhir_server = state.get("fhir_server", "")
        patient_id = state.get("patient_id", "")
        from urllib.parse import urlencode
        params = urlencode({"fhirServiceUrl": fhir_server, "patientId": patient_id})
        launch_url = f"{smart_app_url}?{params}"
        links = [Link(label="Open Sepsis Checklist", url=launch_url, type="smart")]

    card = Card(
        summary=f"Sepsis risk: {risk_level.capitalize()} (qSOFA {qsofa['score']}/3)",
        indicator=indicator,
        source=_SOURCE,
        detail=detail,
        links=links,
    )

    CDSResponse(cards=[card])  # validate
    logger.info("sepsis card_builder | risk=%s indicator=%s", risk_level, indicator)
    return {**state, "cards": [card]}


async def fallback(state: dict[str, Any]) -> dict[str, Any]:
    logger.error("Sepsis agent fallback triggered | error=%s", state.get("error", "unknown"))
    return {**state, "cards": []}
