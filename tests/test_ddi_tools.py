"""Tests for DDI tools — FHIR extraction and curated DDI lookup."""
from __future__ import annotations

import pytest

from app.agents.ddi.tools import (
    check_interactions,
    extract_drug_info,
    extract_drugs_from_bundle,
    extract_drugs_from_draft_orders,
)


# ---------------------------------------------------------------------------
# FHIR extraction tests (pure, no network)
# ---------------------------------------------------------------------------

def _med_request(rxcui: str, display: str, status: str = "active") -> dict:
    return {
        "resourceType": "MedicationRequest",
        "status": status,
        "medicationCodeableConcept": {
            "coding": [
                {
                    "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                    "code": rxcui,
                    "display": display,
                }
            ],
            "text": display,
        },
    }


def test_extract_drug_info_rxnorm():
    rxcui, name = extract_drug_info(_med_request("855332", "Warfarin 5 MG"))
    assert rxcui == "855332"
    assert name == "Warfarin 5 MG"


def test_extract_drug_info_no_coding():
    resource = {"resourceType": "MedicationRequest", "status": "active", "medicationCodeableConcept": {}}
    rxcui, name = extract_drug_info(resource)
    assert rxcui is None
    assert name is None


def test_extract_drugs_from_bundle():
    bundle = {
        "resourceType": "Bundle",
        "entry": [
            {"resource": _med_request("855332", "Warfarin")},
            {"resource": _med_request("1191", "Aspirin")},
        ],
    }
    drugs = extract_drugs_from_bundle(bundle)
    assert len(drugs) == 2
    assert drugs[0]["rxcui"] == "855332"
    assert drugs[1]["rxcui"] == "1191"


def test_extract_drugs_skips_stopped():
    bundle = {
        "resourceType": "Bundle",
        "entry": [
            {"resource": _med_request("855332", "Warfarin", status="stopped")},
            {"resource": _med_request("1191", "Aspirin", status="active")},
        ],
    }
    drugs = extract_drugs_from_bundle(bundle)
    assert len(drugs) == 1
    assert drugs[0]["rxcui"] == "1191"


def test_extract_drugs_from_draft_orders():
    context = {
        "draftOrders": {
            "resourceType": "Bundle",
            "entry": [{"resource": _med_request("855332", "Warfarin", status="draft")}],
        }
    }
    drugs = extract_drugs_from_draft_orders(context)
    assert len(drugs) == 1
    assert drugs[0]["name"] == "Warfarin"


# ---------------------------------------------------------------------------
# Curated DDI lookup (pure, no network)
# ---------------------------------------------------------------------------

def test_warfarin_aspirin_interaction():
    drugs = [
        {"rxcui": "11289", "name": "Warfarin"},
        {"rxcui": "1191", "name": "Aspirin"},
    ]
    interactions = check_interactions(drugs)
    assert len(interactions) > 0
    combined = " ".join(i["drug1"] + i["drug2"] for i in interactions).lower()
    assert "warfarin" in combined and "aspirin" in combined
    assert interactions[0]["severity"] in ("major", "contraindicated")


def test_no_interaction_for_single_drug():
    drugs = [{"rxcui": "11289", "name": "Warfarin"}]
    assert check_interactions(drugs) == []


def test_no_interaction_for_unrelated_drugs():
    drugs = [
        {"rxcui": "99999", "name": "Amoxicillin"},
        {"rxcui": "88888", "name": "Omeprazole"},
    ]
    assert check_interactions(drugs) == []


def test_contraindicated_severity_sorted_first():
    # oxycodone + diazepam (contraindicated) + warfarin + aspirin (major)
    drugs = [
        {"rxcui": "7052", "name": "Oxycodone"},
        {"rxcui": "2537", "name": "Diazepam"},
        {"rxcui": "11289", "name": "Warfarin"},
        {"rxcui": "1191", "name": "Aspirin"},
    ]
    interactions = check_interactions(drugs)
    assert interactions[0]["severity"] == "contraindicated"


def test_name_fallback_matching():
    # Use names without RxCUI codes
    drugs = [
        {"rxcui": "", "name": "Warfarin"},
        {"rxcui": "", "name": "Aspirin"},
    ]
    interactions = check_interactions(drugs)
    assert len(interactions) > 0
