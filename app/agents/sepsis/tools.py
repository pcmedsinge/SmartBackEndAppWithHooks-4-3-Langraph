"""Sepsis agent tools — FHIR vital sign / lab extraction and qSOFA scoring.

All functions work on coded FHIR values only (LOINC codes, numeric values).
No patient identifiers are extracted or passed downstream.
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# LOINC codes used for matching
# ---------------------------------------------------------------------------

LOINC_RESPIRATORY_RATE = "9279-1"
LOINC_SYSTOLIC_BP = "8480-6"
LOINC_BLOOD_PRESSURE_PANEL = "55284-4"
LOINC_GCS_TOTAL = "9269-2"
LOINC_LACTATE = "2524-7"        # Lactate [Moles/volume] in Blood
LOINC_LACTATE_ALT = "59032-3"   # Lactate [Mass/volume] in Blood
LOINC_WBC = "6690-2"            # Leukocytes [#/volume] in Blood


# ---------------------------------------------------------------------------
# FHIR Observation extraction helpers
# ---------------------------------------------------------------------------

def _get_loinc_codes(observation: dict[str, Any]) -> list[str]:
    codes = []
    for coding in observation.get("code", {}).get("coding", []):
        if "loinc" in coding.get("system", "").lower():
            codes.append(coding.get("code", ""))
    return codes


def _get_numeric_value(observation: dict[str, Any]) -> float | None:
    """Extract the primary numeric value from a FHIR Observation."""
    vq = observation.get("valueQuantity")
    if vq and "value" in vq:
        return float(vq["value"])
    # Component-based (e.g. blood pressure panel)
    for component in observation.get("component", []):
        vq = component.get("valueQuantity")
        if vq and "value" in vq:
            return float(vq["value"])
    return None


def _get_component_value(observation: dict[str, Any], loinc_code: str) -> float | None:
    """Extract a value from a specific component within a panel observation."""
    for component in observation.get("component", []):
        codes = [c.get("code", "") for c in component.get("code", {}).get("coding", [])]
        if loinc_code in codes:
            vq = component.get("valueQuantity")
            if vq and "value" in vq:
                return float(vq["value"])
    return None


def extract_vitals(bundle: dict[str, Any]) -> dict[str, float | None]:
    """Extract the most recent vital sign values from an Observation Bundle.

    Returns dict with keys: respiratory_rate, systolic_bp, gcs_total.
    Values are float or None if not found.
    """
    vitals: dict[str, float | None] = {
        "respiratory_rate": None,
        "systolic_bp": None,
        "gcs_total": None,
    }

    for entry in bundle.get("entry", []):
        obs = entry.get("resource", {})
        if obs.get("resourceType") != "Observation":
            continue
        if obs.get("status") in ("cancelled", "entered-in-error"):
            continue

        codes = _get_loinc_codes(obs)

        if LOINC_RESPIRATORY_RATE in codes and vitals["respiratory_rate"] is None:
            vitals["respiratory_rate"] = _get_numeric_value(obs)

        if LOINC_SYSTOLIC_BP in codes and vitals["systolic_bp"] is None:
            vitals["systolic_bp"] = _get_numeric_value(obs)

        # Systolic BP may be a component inside a BP panel
        if LOINC_BLOOD_PRESSURE_PANEL in codes and vitals["systolic_bp"] is None:
            vitals["systolic_bp"] = _get_component_value(obs, LOINC_SYSTOLIC_BP)

        if LOINC_GCS_TOTAL in codes and vitals["gcs_total"] is None:
            vitals["gcs_total"] = _get_numeric_value(obs)

    return vitals


def extract_labs(bundle: dict[str, Any]) -> dict[str, float | None]:
    """Extract lactate and WBC from a lab Observation Bundle."""
    labs: dict[str, float | None] = {"lactate": None, "wbc": None}

    for entry in bundle.get("entry", []):
        obs = entry.get("resource", {})
        if obs.get("resourceType") != "Observation":
            continue
        if obs.get("status") in ("cancelled", "entered-in-error"):
            continue

        codes = _get_loinc_codes(obs)

        if (LOINC_LACTATE in codes or LOINC_LACTATE_ALT in codes) and labs["lactate"] is None:
            labs["lactate"] = _get_numeric_value(obs)

        if LOINC_WBC in codes and labs["wbc"] is None:
            labs["wbc"] = _get_numeric_value(obs)

    return labs


# ---------------------------------------------------------------------------
# qSOFA scoring (pure function — no I/O)
# ---------------------------------------------------------------------------

def score_qsofa(vitals: dict[str, float | None]) -> dict[str, Any]:
    """Score qSOFA criteria from extracted vital signs.

    Criteria (each criterion = 1 point, max = 3):
      - Respiratory rate >= 22 breaths/min
      - Systolic BP <= 100 mmHg
      - Altered mentation (GCS < 15; or None = assumed normal = 0)

    Returns:
        score       — int 0–3
        criteria    — list of met criteria descriptions
        raw_vitals  — the input values (no PHI)
    """
    score = 0
    criteria: list[str] = []

    rr = vitals.get("respiratory_rate")
    sbp = vitals.get("systolic_bp")
    gcs = vitals.get("gcs_total")

    if rr is not None and rr >= 22:
        score += 1
        criteria.append(f"Respiratory rate {rr:.0f} breaths/min (≥22)")

    if sbp is not None and sbp <= 100:
        score += 1
        criteria.append(f"Systolic BP {sbp:.0f} mmHg (≤100)")

    if gcs is not None and gcs < 15:
        score += 1
        criteria.append(f"Altered mentation (GCS {gcs:.0f})")

    return {
        "score": score,
        "criteria": criteria,
        "raw_vitals": {
            "respiratory_rate": rr,
            "systolic_bp": sbp,
            "gcs_total": gcs,
        },
    }
