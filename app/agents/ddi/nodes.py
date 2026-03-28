from __future__ import annotations

import logging
import os
from typing import Any

from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.agents.ddi.tools import (
    check_interactions,
    extract_drugs_from_bundle,
    extract_drugs_from_draft_orders,
)
from app.fhir.client import FHIRClient, bundle_entries, resolve
from app.models.cards import Card, CDSResponse, Indicator, Source

logger = logging.getLogger(__name__)

_SOURCE = Source(label="ClinAgent — DDI", url="https://github.com/clinagent")


# ---------------------------------------------------------------------------
# Structured output schema for the LLM reasoner
# ---------------------------------------------------------------------------

class DDIReasonerOutput(BaseModel):
    interaction_found: bool
    severity: str  # "none" | "minor" | "moderate" | "major" | "contraindicated"
    drug_pair: str  # e.g. "Warfarin + Aspirin"
    explanation: str  # clinical reasoning — NO patient identifiers
    recommendation: str  # actionable next step for the clinician


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------

async def context_parser(state: dict[str, Any]) -> dict[str, Any]:
    """Extract patientId, fhirServer, token, and draft drug codes from hook state."""
    req = state["hook_request"]
    context = req.get("context", {})

    patient_id = context.get("patientId", "")
    fhir_server = req.get("fhirServer") or os.getenv("FHIR_SERVER_URL", "https://r4.smarthealthit.org")
    token = None
    auth = req.get("fhirAuthorization")
    if auth:
        token = auth.get("access_token")

    draft_drugs = extract_drugs_from_draft_orders(context)
    logger.info("context_parser | patient=%s draft_drugs=%d", patient_id, len(draft_drugs))

    return {
        **state,
        "patient_id": patient_id,
        "fhir_server": fhir_server,
        "token": token,
        "draft_drugs": draft_drugs,
    }


async def fhir_fetcher(state: dict[str, Any]) -> dict[str, Any]:
    """Fetch active medications from FHIR (prefetch first, live fallback)."""
    client = FHIRClient(base_url=state["fhir_server"], token=state.get("token"))
    prefetch = state["hook_request"].get("prefetch")

    bundle = await resolve(
        prefetch,
        "medications",
        client,
        "MedicationRequest",
        state["patient_id"],
        extra_params={"status": "active"},
    )

    active_drugs = extract_drugs_from_bundle(bundle)
    logger.info("fhir_fetcher | active_medications=%d", len(active_drugs))

    # Combine draft + active, deduplicate by rxcui
    seen: set[str] = set()
    all_drugs: list[dict[str, str]] = []
    for drug in state["draft_drugs"] + active_drugs:
        key = drug["rxcui"] or drug["name"]
        if key not in seen:
            seen.add(key)
            all_drugs.append(drug)

    return {**state, "active_drugs": active_drugs, "all_drugs": all_drugs}


async def interaction_checker(state: dict[str, Any]) -> dict[str, Any]:
    """Check all drug codes against the curated DDI dataset."""
    all_drugs = state.get("all_drugs", [])
    interactions = check_interactions(all_drugs)
    logger.info("interaction_checker | drugs=%d interactions=%d", len(all_drugs), len(interactions))
    return {**state, "interactions": interactions}


async def llm_reasoner(state: dict[str, Any]) -> dict[str, Any]:
    """Use GPT-4o to explain the interaction. Only coded drug data is sent — no PHI."""
    interactions = state["interactions"]
    all_drugs = state.get("all_drugs", [])

    drug_list = ", ".join(d["name"] for d in all_drugs) or "No drugs identified"
    interaction_text = "\n".join(
        f"- {i['drug1']} + {i['drug2']} | severity: {i['severity']} | {i['description']}"
        for i in interactions
    )

    system_prompt = (
        "You are a clinical pharmacology assistant embedded in an EHR clinical decision support system. "
        "You receive a list of drug names and confirmed drug interaction records from the RxNorm database. "
        "Your job is to explain the interaction in plain clinical language and recommend an action for the clinician. "
        "IMPORTANT: Do NOT include any patient identifiers (name, DOB, MRN, age, sex) in your response. "
        "Respond only about the drug interaction itself."
    )

    user_prompt = (
        f"Medications involved:\n{drug_list}\n\n"
        f"Confirmed interactions from RxNorm:\n{interaction_text}\n\n"
        "Based on the most clinically significant interaction above, provide your assessment."
    )

    try:
        llm = ChatOpenAI(model="gpt-4o", temperature=0).with_structured_output(DDIReasonerOutput)
        output: DDIReasonerOutput = await llm.ainvoke(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )
    except Exception as exc:
        logger.exception("llm_reasoner failed: %s", exc)
        # Degrade gracefully: build a card from the raw interaction data without LLM explanation
        top = interactions[0]
        output = DDIReasonerOutput(
            interaction_found=True,
            severity=top["severity"],
            drug_pair=f"{top['drug1']} + {top['drug2']}",
            explanation=top["description"],
            recommendation="Review the interaction and consider an alternative medication.",
        )

    logger.info(
        "llm_reasoner | interaction_found=%s severity=%s pair=%s",
        output.interaction_found,
        output.severity,
        output.drug_pair,
    )
    return {**state, "llm_output": output}


async def card_builder(state: dict[str, Any]) -> dict[str, Any]:
    """Convert LLM output into a validated CDS card."""
    output: DDIReasonerOutput = state["llm_output"]

    if not output.interaction_found or output.severity == "none":
        return {**state, "cards": []}

    severity_to_indicator = {
        "minor": Indicator.info,
        "moderate": Indicator.warning,
        "major": Indicator.warning,
        "contraindicated": Indicator.critical,
    }
    indicator = severity_to_indicator.get(output.severity.lower(), Indicator.warning)

    card = Card(
        summary=f"Drug interaction: {output.drug_pair} ({output.severity})",
        indicator=indicator,
        source=_SOURCE,
        detail=f"{output.explanation}\n\n**Recommendation:** {output.recommendation}",
    )

    # Validate before returning
    CDSResponse(cards=[card])
    logger.info("card_builder | card built indicator=%s", indicator)
    return {**state, "cards": [card]}


async def fallback(state: dict[str, Any]) -> dict[str, Any]:
    """Catch-all — always returns empty cards so the endpoint never 500s."""
    logger.error("DDI agent fallback triggered | error=%s", state.get("error", "unknown"))
    return {**state, "cards": []}
