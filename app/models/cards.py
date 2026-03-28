from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, HttpUrl


class Indicator(str, Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


class Source(BaseModel):
    label: str
    url: str | None = None
    icon: str | None = None


class Coding(BaseModel):
    system: str
    code: str
    display: str | None = None


class Action(BaseModel):
    type: str  # "create" | "update" | "delete"
    description: str
    resource: dict[str, Any] | None = None


class Suggestion(BaseModel):
    label: str
    uuid: str | None = None
    isRecommended: bool | None = None
    actions: list[Action] = []


class Link(BaseModel):
    label: str
    url: str
    type: str  # "absolute" | "smart"
    appContext: str | None = None


class Card(BaseModel):
    summary: str
    indicator: Indicator
    source: Source
    detail: str | None = None
    suggestions: list[Suggestion] = []
    selectionBehavior: str | None = None
    overrideReasons: list[Coding] = []
    links: list[Link] = []
    uuid: str | None = None


class CDSResponse(BaseModel):
    cards: list[Card]
    systemActions: list[Action] = []
