"""Smoke tests for FHIRClient — hit the open SMART sandbox (no auth needed)."""
from __future__ import annotations

import asyncio
import pytest

from app.fhir.client import FHIRClient, bundle_entries, resolve

FHIR_BASE = "https://r4.smarthealthit.org"
PATIENT_ID = "87a339d0-8cae-418e-89c7-8651e6aab3c6"  # open sandbox patient


@pytest.mark.asyncio
async def test_get_medication_requests():
    client = FHIRClient(base_url=FHIR_BASE)
    bundle = await client.get_resource("MedicationRequest", PATIENT_ID)
    assert bundle["resourceType"] == "Bundle"
    entries = bundle_entries(bundle)
    print(f"MedicationRequest entries: {len(entries)}")


@pytest.mark.asyncio
async def test_prefetch_short_circuits_http():
    fake_bundle = {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": 1,
        "entry": [{"resource": {"resourceType": "MedicationRequest", "id": "test-1"}}],
    }
    prefetch = {"medications": fake_bundle}
    client = FHIRClient(base_url=FHIR_BASE)

    result = await resolve(prefetch, "medications", client, "MedicationRequest", PATIENT_ID)
    assert result == fake_bundle  # came from prefetch, not HTTP


@pytest.mark.asyncio
async def test_prefetch_miss_falls_back_to_live():
    client = FHIRClient(base_url=FHIR_BASE)
    result = await resolve({}, "medications", client, "MedicationRequest", PATIENT_ID)
    assert result["resourceType"] == "Bundle"


@pytest.mark.asyncio
async def test_timeout_returns_empty_bundle():
    # Point at a non-routable address to trigger a timeout
    client = FHIRClient(base_url="http://10.255.255.1")
    bundle = await client.get_resource("MedicationRequest", "any-patient")
    assert bundle["resourceType"] == "Bundle"
    assert bundle["total"] == 0
