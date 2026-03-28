from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.ddi.nodes import (
    card_builder,
    context_parser,
    fallback,
    fhir_fetcher,
    interaction_checker,
    llm_reasoner,
)
from app.models.cards import CDSResponse

logger = logging.getLogger(__name__)


def _has_interactions(state: dict[str, Any]) -> str:
    """Conditional edge: route to llm_reasoner only if interactions were found."""
    if state.get("interactions"):
        return "llm_reasoner"
    logger.info("DDI graph | no interactions found — returning empty cards")
    return "empty_cards"


async def _empty_cards(state: dict[str, Any]) -> dict[str, Any]:
    return {**state, "cards": []}


def build_ddi_graph() -> Any:
    """Build and compile the DDI LangGraph StateGraph."""
    graph = StateGraph(dict)

    graph.add_node("context_parser", context_parser)
    graph.add_node("fhir_fetcher", fhir_fetcher)
    graph.add_node("interaction_checker", interaction_checker)
    graph.add_node("llm_reasoner", llm_reasoner)
    graph.add_node("card_builder", card_builder)
    graph.add_node("empty_cards", _empty_cards)
    graph.add_node("fallback", fallback)

    graph.set_entry_point("context_parser")
    graph.add_edge("context_parser", "fhir_fetcher")
    graph.add_edge("fhir_fetcher", "interaction_checker")
    graph.add_conditional_edges("interaction_checker", _has_interactions)
    graph.add_edge("llm_reasoner", "card_builder")
    graph.add_edge("card_builder", END)
    graph.add_edge("empty_cards", END)
    graph.add_edge("fallback", END)

    return graph.compile()


# Module-level compiled graph — instantiated once at import time
ddi_graph = build_ddi_graph()


async def run_ddi_agent(hook_request: dict[str, Any]) -> CDSResponse:
    """Entry point called by the FastAPI endpoint.

    Always returns a CDSResponse — never raises.
    """
    initial_state: dict[str, Any] = {
        "hook_request": hook_request,
        "patient_id": "",
        "fhir_server": "",
        "token": None,
        "draft_drugs": [],
        "active_drugs": [],
        "all_drugs": [],
        "interactions": [],
        "llm_output": None,
        "cards": [],
        "error": None,
    }

    try:
        final_state = await ddi_graph.ainvoke(initial_state)
        cards = final_state.get("cards", [])
        return CDSResponse(cards=cards)
    except Exception as exc:
        logger.exception("DDI graph unhandled exception: %s", exc)
        return CDSResponse(cards=[])
