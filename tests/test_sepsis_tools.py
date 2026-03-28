"""Tests for Sepsis tools — FHIR extraction and qSOFA scoring (pure, no network)."""
from __future__ import annotations

from app.agents.sepsis.tools import extract_vitals, extract_labs, score_qsofa


def _obs(loinc: str, value: float, status: str = "final") -> dict:
    return {
        "resource": {
            "resourceType": "Observation",
            "status": status,
            "code": {
                "coding": [{"system": "http://loinc.org", "code": loinc}]
            },
            "valueQuantity": {"value": value, "unit": "unit"},
        }
    }


def _bp_panel(sbp: float, dbp: float) -> dict:
    return {
        "resource": {
            "resourceType": "Observation",
            "status": "final",
            "code": {
                "coding": [{"system": "http://loinc.org", "code": "55284-4"}]
            },
            "component": [
                {
                    "code": {"coding": [{"system": "http://loinc.org", "code": "8480-6"}]},
                    "valueQuantity": {"value": sbp},
                },
                {
                    "code": {"coding": [{"system": "http://loinc.org", "code": "8462-4"}]},
                    "valueQuantity": {"value": dbp},
                },
            ],
        }
    }


def _bundle(*entries) -> dict:
    return {"resourceType": "Bundle", "entry": list(entries)}


# ---------------------------------------------------------------------------
# extract_vitals
# ---------------------------------------------------------------------------

def test_extract_rr_sbp_gcs():
    bundle = _bundle(
        _obs("9279-1", 24),   # RR
        _obs("8480-6", 95),   # SBP
        _obs("9269-2", 13),   # GCS
    )
    vitals = extract_vitals(bundle)
    assert vitals["respiratory_rate"] == 24
    assert vitals["systolic_bp"] == 95
    assert vitals["gcs_total"] == 13


def test_extract_sbp_from_bp_panel():
    bundle = _bundle(_bp_panel(sbp=98, dbp=60))
    vitals = extract_vitals(bundle)
    assert vitals["systolic_bp"] == 98


def test_skips_cancelled_observations():
    bundle = _bundle(_obs("9279-1", 30, status="cancelled"))
    vitals = extract_vitals(bundle)
    assert vitals["respiratory_rate"] is None


def test_empty_bundle_returns_none_values():
    vitals = extract_vitals({"resourceType": "Bundle", "entry": []})
    assert all(v is None for v in vitals.values())


# ---------------------------------------------------------------------------
# extract_labs
# ---------------------------------------------------------------------------

def test_extract_lactate_and_wbc():
    bundle = _bundle(
        _obs("2524-7", 3.2),   # lactate
        _obs("6690-2", 14.5),  # WBC
    )
    labs = extract_labs(bundle)
    assert labs["lactate"] == 3.2
    assert labs["wbc"] == 14.5


# ---------------------------------------------------------------------------
# score_qsofa
# ---------------------------------------------------------------------------

def test_qsofa_score_3():
    vitals = {"respiratory_rate": 24, "systolic_bp": 95, "gcs_total": 13}
    result = score_qsofa(vitals)
    assert result["score"] == 3
    assert len(result["criteria"]) == 3


def test_qsofa_score_0_normal_vitals():
    vitals = {"respiratory_rate": 18, "systolic_bp": 120, "gcs_total": 15}
    result = score_qsofa(vitals)
    assert result["score"] == 0
    assert result["criteria"] == []


def test_qsofa_score_1_high_rr_only():
    vitals = {"respiratory_rate": 22, "systolic_bp": 120, "gcs_total": 15}
    result = score_qsofa(vitals)
    assert result["score"] == 1


def test_qsofa_none_vitals_score_0():
    vitals = {"respiratory_rate": None, "systolic_bp": None, "gcs_total": None}
    result = score_qsofa(vitals)
    assert result["score"] == 0


def test_qsofa_boundary_rr_exactly_22():
    vitals = {"respiratory_rate": 22, "systolic_bp": None, "gcs_total": None}
    result = score_qsofa(vitals)
    assert result["score"] == 1


def test_qsofa_boundary_sbp_exactly_100():
    vitals = {"respiratory_rate": None, "systolic_bp": 100, "gcs_total": None}
    result = score_qsofa(vitals)
    assert result["score"] == 1
