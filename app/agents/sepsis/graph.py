from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.sepsis.nodes import (
    card_builder,
    context_parser,
    fallback,
    lab_fetcher,
    llm_reasoner,
    vitals_fetcher,
)
from app.models.cards import CDSResponse

logger = logging.getLogger(__name__)


def _route_after_vitals(state: dict[str, Any]) -> str:
    """Skip LLM entirely if qSOFA = 0 — saves latency and cost."""
    score = state.get("qsofa", {}).get("score", 0)
    if score == 0:
        logger.info("Sepsis graph | qSOFA=0 — returning empty cards (no LLM call)")
        return "empty_cards"
    return "lab_fetcher"


async def _empty_cards(state: dict[str, Any]) -> dict[str, Any]:
    return {**state, "cards": []}


def build_sepsis_graph() -> Any:
    graph = StateGraph(dict)

    graph.add_node("context_parser", context_parser)
    graph.add_node("vitals_fetcher", vitals_fetcher)
    graph.add_node("lab_fetcher", lab_fetcher)
    graph.add_node("llm_reasoner", llm_reasoner)
    graph.add_node("card_builder", card_builder)
    graph.add_node("empty_cards", _empty_cards)
    graph.add_node("fallback", fallback)

    graph.set_entry_point("context_parser")
    graph.add_edge("context_parser", "vitals_fetcher")
    graph.add_conditional_edges("vitals_fetcher", _route_after_vitals)
    graph.add_edge("lab_fetcher", "llm_reasoner")
    graph.add_edge("llm_reasoner", "card_builder")
    graph.add_edge("card_builder", END)
    graph.add_edge("empty_cards", END)
    graph.add_edge("fallback", END)

    return graph.compile()


sepsis_graph = build_sepsis_graph()


async def run_sepsis_agent(hook_request: dict[str, Any]) -> CDSResponse:
    """Entry point called by the FastAPI endpoint. Always returns CDSResponse."""
    initial_state: dict[str, Any] = {
        "hook_request": hook_request,
        "patient_id": "",
        "fhir_server": "",
        "token": None,
        "vitals": {},
        "qsofa": {"score": 0, "criteria": [], "raw_vitals": {}},
        "labs": {},
        "llm_output": None,
        "cards": [],
        "error": None,
    }

    try:
        final_state = await sepsis_graph.ainvoke(initial_state)
        return CDSResponse(cards=final_state.get("cards", []))
    except Exception as exc:
        logger.exception("Sepsis graph unhandled exception: %s", exc)
        return CDSResponse(cards=[])
