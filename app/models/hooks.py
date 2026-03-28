from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class FHIRAuthorization(BaseModel):
    access_token: str
    token_type: str
    expires_in: int | None = None
    scope: str | None = None
    subject: str | None = None


class CDSRequest(BaseModel):
    hookInstance: str
    hook: str
    context: dict[str, Any]
    fhirServer: str | None = None
    fhirAuthorization: FHIRAuthorization | None = None
    prefetch: dict[str, Any] | None = None


class CDSService(BaseModel):
    hook: str
    title: str
    description: str
    id: str
    prefetch: dict[str, str] | None = None


class CDSServiceDiscovery(BaseModel):
    services: list[CDSService]
