"""Seed local HAPI FHIR server with test patients for ClinAgent demo.

Usage:
    python tests/seed_fhir.py

Creates:
  - Patient: John Testpatient
    - Active Warfarin + Simvastatin (DDI testing)
    - Abnormal vitals: RR=24, SBP=92, GCS=13 (Sepsis testing, qSOFA=3)

  - Patient: Jane Healthypatient
    - Normal vitals (qSOFA=0, no cards expected)
"""
import json
import sys
import httpx

FHIR_BASE = "http://localhost:8082/fhir"
HEADERS = {"Content-Type": "application/fhir+json", "Accept": "application/fhir+json"}


def post(resource: dict) -> dict:
    resource_type = resource["resourceType"]
    resp = httpx.post(f"{FHIR_BASE}/{resource_type}", json=resource, headers=HEADERS, timeout=10)
    if resp.status_code not in (200, 201):
        print(f"  ERROR {resp.status_code}: {resp.text[:200]}")
        sys.exit(1)
    created = resp.json()
    print(f"  Created {resource_type}/{created['id']}")
    return created


def med_request(patient_id: str, rxcui: str, display: str, status: str = "active") -> dict:
    return {
        "resourceType": "MedicationRequest",
        "status": status,
        "intent": "order",
        "subject": {"reference": f"Patient/{patient_id}"},
        "medicationCodeableConcept": {
            "coding": [{
                "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                "code": rxcui,
                "display": display,
            }],
            "text": display,
        },
    }


# Future date ensures our seeded observations sort before Synthea historical data (_sort=-date)
EFFECTIVE_DATE = "2099-01-01T00:00:00+00:00"


def observation(patient_id: str, loinc: str, display: str, value: float, unit: str) -> dict:
    return {
        "resourceType": "Observation",
        "status": "final",
        "effectiveDateTime": EFFECTIVE_DATE,
        "category": [{"coding": [{
            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
            "code": "vital-signs",
        }]}],
        "code": {
            "coding": [{"system": "http://loinc.org", "code": loinc, "display": display}],
            "text": display,
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "valueQuantity": {"value": value, "unit": unit, "system": "http://unitsofmeasure.org"},
    }


def bp_observation(patient_id: str, sbp: float, dbp: float) -> dict:
    return {
        "resourceType": "Observation",
        "status": "final",
        "effectiveDateTime": EFFECTIVE_DATE,
        "category": [{"coding": [{
            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
            "code": "vital-signs",
        }]}],
        "code": {
            "coding": [{"system": "http://loinc.org", "code": "55284-4", "display": "Blood pressure panel"}],
            "text": "Blood pressure",
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "component": [
            {
                "code": {"coding": [{"system": "http://loinc.org", "code": "8480-6", "display": "Systolic BP"}]},
                "valueQuantity": {"value": sbp, "unit": "mmHg"},
            },
            {
                "code": {"coding": [{"system": "http://loinc.org", "code": "8462-4", "display": "Diastolic BP"}]},
                "valueQuantity": {"value": dbp, "unit": "mmHg"},
            },
        ],
    }


def main():
    print(f"\nSeeding {FHIR_BASE} ...\n")

    # ── Patient 1: John Testpatient (DDI + Sepsis risk) ──────────────────────
    print("Creating Patient: John Testpatient (DDI + high sepsis risk)")
    john = post({
        "resourceType": "Patient",
        "name": [{"family": "Testpatient", "given": ["John"]}],
        "gender": "male",
        "birthDate": "1960-01-01",
    })
    jid = john["id"]

    print("  Adding active medications (Warfarin + Simvastatin)...")
    post(med_request(jid, "11289", "Warfarin 5 MG Oral Tablet"))
    post(med_request(jid, "36567", "Simvastatin 20 MG Oral Tablet"))

    print("  Adding abnormal vitals (qSOFA=3: RR=24, SBP=92, GCS=13)...")
    post(observation(jid, "9279-1", "Respiratory rate", 24, "/min"))
    post(bp_observation(jid, sbp=92, dbp=60))
    post(observation(jid, "9269-2", "Glasgow Coma Score", 13, "{score}"))

    print(f"\n  John Testpatient ID: {jid}")
    print(f"  DDI test : order Aspirin or Clarithromycin → should get warning/contraindicated card")
    print(f"  Sepsis test: open patient-view → should get HIGH RISK card (qSOFA=3)")

    # ── Patient 2: Jane Healthypatient (no cards expected) ───────────────────
    print("\nCreating Patient: Jane Healthypatient (normal vitals, no DDI)")
    jane = post({
        "resourceType": "Patient",
        "name": [{"family": "Healthypatient", "given": ["Jane"]}],
        "gender": "female",
        "birthDate": "1985-06-15",
    })
    jnid = jane["id"]

    print("  Adding normal vitals (qSOFA=0)...")
    post(observation(jnid, "9279-1", "Respiratory rate", 16, "/min"))
    post(bp_observation(jnid, sbp=120, dbp=80))
    post(observation(jnid, "9269-2", "Glasgow Coma Score", 15, "{score}"))

    print(f"\n  Jane Healthypatient ID: {jnid}")
    print(f"  Expected: no cards (qSOFA=0, no DDI medications)")

    print("\nDone! Set sandbox FHIR server to: http://localhost:8082/fhir")
    print("Search for 'Testpatient' or 'Healthypatient' in the patient list.\n")


def reseed_demo_vitals():
    """Re-seed abnormal vitals for the existing demo patients with effectiveDateTime=2099
    so they sort before Synthea historical data (_sort=-date&_count=10 prefetch).

    Demo patient HAPI IDs (already seeded with meds):
      Robbi844  → 66235
      Ramon749  → 51707
      Karena692 → 65520
    """
    demo_ids = ["66235", "51707", "65520"]
    print(f"\nRe-seeding abnormal vitals for demo patients {demo_ids} ...\n")
    for pid in demo_ids:
        print(f"  Patient/{pid}")
        post(observation(pid, "9279-1", "Respiratory rate", 24, "/min"))
        post(bp_observation(pid, sbp=92, dbp=60))
        post(observation(pid, "9269-2", "Glasgow Coma Score", 13, "{score}"))
    print("\nDone! Each patient now has RR=24, SBP=92, GCS=13 dated 2099-01-01.")
    print("qSOFA=3 -> HIGH RISK card expected on Patient View.\n")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "reseed":
        reseed_demo_vitals()
    else:
        main()
