from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Hard timeout for any single FHIR request — keeps us inside the 500ms budget
_TIMEOUT = httpx.Timeout(connect=1.0, read=2.0, write=2.0, pool=1.0)


class FHIRClient:
    """Thin FHIR R4 client for the SMART backend app pattern.

    Usage:
        client = FHIRClient(base_url="https://r4.smarthealthit.org", token="Bearer ...")
        bundle = await client.get_resource("MedicationRequest", patient_id="SMART-1288992")
    """

    def __init__(self, base_url: str, token: str | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers: dict[str, str] = {"Accept": "application/fhir+json"}
        if token:
            self._headers["Authorization"] = f"Bearer {token}" if not token.startswith("Bearer") else token

    async def get_resource(
        self,
        resource_type: str,
        patient_id: str,
        extra_params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Fetch a FHIR resource Bundle for the given patient.

        Returns a FHIR Bundle dict, or an empty Bundle on error.
        """
        params: dict[str, str] = {"patient": patient_id}
        if extra_params:
            params.update(extra_params)

        url = f"{self._base_url}/{resource_type}"
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
                resp = await http.get(url, headers=self._headers, params=params)
                resp.raise_for_status()
                return resp.json()
        except httpx.TimeoutException:
            logger.warning("FHIR timeout fetching %s for patient %s", resource_type, patient_id)
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "FHIR %s error fetching %s: %s",
                exc.response.status_code,
                resource_type,
                exc.response.text[:200],
            )
        except Exception as exc:
            logger.warning("FHIR fetch error for %s: %s", resource_type, exc)

        return _empty_bundle()

    async def get_by_id(self, resource_type: str, resource_id: str) -> dict[str, Any]:
        """Fetch a single FHIR resource by type and ID."""
        url = f"{self._base_url}/{resource_type}/{resource_id}"
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
                resp = await http.get(url, headers=self._headers)
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logger.warning("FHIR get_by_id error %s/%s: %s", resource_type, resource_id, exc)
            return {}


def resolve(
    prefetch: dict[str, Any] | None,
    key: str,
    client: FHIRClient,
    resource_type: str,
    patient_id: str,
    extra_params: dict[str, str] | None = None,
):
    """Return a coroutine that resolves a FHIR resource.

    Checks prefetch first; falls back to a live FHIR fetch.
    Always returns a coroutine so callers can await it uniformly.

    Example:
        meds = await resolve(prefetch, "medications", client, "MedicationRequest", patient_id)
    """
    if prefetch and key in prefetch and prefetch[key]:
        data = prefetch[key]
        logger.debug("Using prefetch[%s] (%d entries)", key, _entry_count(data))

        async def _prefetch_result() -> dict[str, Any]:
            return data

        return _prefetch_result()

    logger.debug("Prefetch miss for '%s' — fetching live from FHIR", key)
    return client.get_resource(resource_type, patient_id, extra_params)


def bundle_entries(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract the list of resource dicts from a FHIR Bundle."""
    return [e["resource"] for e in bundle.get("entry", []) if "resource" in e]


def _empty_bundle() -> dict[str, Any]:
    return {"resourceType": "Bundle", "type": "searchset", "total": 0, "entry": []}


def _entry_count(bundle: dict[str, Any]) -> int:
    return len(bundle.get("entry", []))
