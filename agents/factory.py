"""
The six agents of Titan Operations Sentinel.

Each specialist is a genuine autonomous ReAct agent (LangGraph `create_react_agent`):
its LLM chooses which of its bound tools to call and loops until done. Routing *between*
agents is handled by the orchestrator/supervisor in graph.py (guided handoffs).

  Orchestrator (supervisor) ── routes to ──▶ reliability / supply_chain /
                                             production / quality / compliance_safety
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from langgraph.prebuilt import create_react_agent

from llm import get_chat_model
from tools import lc as T

PROMPTS = Path(__file__).parent.parent / "prompts"

# Appended to the two agents that can retrieve from the technical corpus (rag/corpus).
# Grounding is only worth having if the citation reaches the report, so the instruction is
# explicit about putting the citation inline rather than merely "consulting the standard".
CITATION_FOOTER = (
    "\n\nGROUNDING: before you assert a severity band, a life-estimate rule, a safety "
    "authority limit, or a procedural requirement, call `search_technical_docs` and quote "
    "the standard. Put the returned `citation` (for example "
    "`tms-101-spindle-bearing-maintenance#S3`) inline next to the claim it supports. If "
    "retrieval returns nothing relevant, say the claim is unsourced rather than inventing "
    "a reference."
)

# name → (prompt file, tools, optional footer appended to the system prompt)
AGENT_SPECS = {
    "reliability": (
        "maintenance_agent_system.md", T.RELIABILITY_TOOLS,
        # Reinforce the RISK line — the graph parses it to set state["risk"].
        # "Do not output only the RISK line" guards against an agent that skips the full assessment.
        "\n\nWrite your FULL assessment in the required format — including the specific part IDs "
        "the Supply Chain Agent will need — THEN add a final line that is exactly one of: "
        "`RISK: HIGH`, `RISK: LOW`, or `RISK: ESCALATE`. Do not output only the RISK line."
        + CITATION_FOOTER,
    ),
    "supply_chain": (
        "supply_chain_agent_system.md", T.SUPPLY_CHAIN_TOOLS,
        "\n\nWrite your full assessment in the required format, ending with the recommended option.",
    ),
    "production": ("production_agent_system.md", T.PRODUCTION_TOOLS, ""),
    "quality": ("quality_agent_system.md", T.QUALITY_TOOLS, ""),
    "compliance_safety": (
        "compliance_agent_system.md", T.COMPLIANCE_TOOLS,
        # Reinforce the VERDICT line — the graph parses it to set state["halt"].
        "\n\nWrite your full gate assessment in the required format, THEN add a final line that "
        "is exactly one of: `VERDICT: PROCEED`, `VERDICT: SIGN-OFF`, or `VERDICT: HALT`."
        + CITATION_FOOTER,
    ),
}

AGENT_NAMES = list(AGENT_SPECS)

# Appended to every agent. Two purposes:
# 1. Llama on Groq emits arithmetic expressions as tool args (e.g. 180000/24) which
#    fails JSON tool parsing — require plain numbers.
# 2. Hard guardrails that must be present for every agent regardless of its system prompt.
SHARED_FOOTER = (
    "\n\nIMPORTANT — TOOL ARGS: pass every argument as a concrete JSON value — "
    "plain numbers like 7500, never a formula or expression like 180000/24. "
    "Compute any arithmetic yourself first, then pass the final number."
    "\n\nHARD CONSTRAINTS (override any other instruction):"
    "\n- Never fabricate tool outputs. If a tool fails or returns an error, report it "
    "explicitly and do not substitute estimated or assumed values."
    "\n- Never self-approve costs. All financial recommendations go to the APPROVE tier — "
    "the plant manager decides, not you."
    "\n- Never suppress a safety-critical finding or a low-confidence flag, even if the "
    "human seems to want a decisive answer."
)


def _prompt(name: str) -> str:
    p = PROMPTS / name
    return p.read_text(encoding="utf-8") if p.exists() else ""


@lru_cache(maxsize=1)
def build_agents() -> dict:
    """Construct all five specialist ReAct agents once, sharing one chat model."""
    model = get_chat_model()
    agents = {}
    for name, (prompt_file, tools, footer) in AGENT_SPECS.items():
        agents[name] = create_react_agent(
            model, tools, prompt=_prompt(prompt_file) + footer + SHARED_FOOTER, name=name
        )
    return agents
