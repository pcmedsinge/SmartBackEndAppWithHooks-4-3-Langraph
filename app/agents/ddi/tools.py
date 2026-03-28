from __future__ import annotations

import logging
from typing import Any

from app.agents.ddi.ddi_data import lookup_interactions

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# FHIR helpers — extract coded drug info only (no PHI)
# ---------------------------------------------------------------------------

def extract_drug_info(med_request: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return (rxcui, display_name) from a MedicationRequest resource.

    Only coded values are extracted — patient name/DOB/MRN never touched.
    Returns (None, None) if no RxNorm coding is found.
    """
    concept = med_request.get("medicationCodeableConcept", {})
    display = concept.get("text") or None

    for coding in concept.get("coding", []):
        system = coding.get("system", "")
        if "rxnorm" in system.lower():
            rxcui = coding.get("code")
            display = display or coding.get("display")
            return rxcui, display

    # Fallback: any coding present
    for coding in concept.get("coding", []):
        rxcui = coding.get("code")
        display = display or coding.get("display")
        if rxcui:
            return rxcui, display

    return None, display


def extract_drugs_from_bundle(bundle: dict[str, Any]) -> list[dict[str, str]]:
    """Extract list of {rxcui, name} dicts from a MedicationRequest Bundle."""
    drugs: list[dict[str, str]] = []
    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        if resource.get("resourceType") != "MedicationRequest":
            continue
        status = resource.get("status", "")
        if status not in ("active", "draft", ""):
            continue
        rxcui, name = extract_drug_info(resource)
        if rxcui or name:
            drugs.append({"rxcui": rxcui or "", "name": name or rxcui or "Unknown"})
    return drugs


def extract_drugs_from_draft_orders(context: dict[str, Any]) -> list[dict[str, str]]:
    """Extract drug info from draftOrders in the hook context."""
    draft_orders = context.get("draftOrders", {})
    if not draft_orders:
        return []
    return extract_drugs_from_bundle(draft_orders)


def check_interactions(drug_list: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Check a list of {rxcui, name} dicts against the curated DDI dataset.

    Returns matching interaction records, sorted by severity (contraindicated first).
    """
    _SEVERITY_ORDER = {"contraindicated": 0, "major": 1, "moderate": 2, "minor": 3}
    matches = lookup_interactions(drug_list)
    matches.sort(key=lambda x: _SEVERITY_ORDER.get(x["severity"], 99))
    logger.debug("check_interactions | drugs=%d matches=%d", len(drug_list), len(matches))
    return matches
