"""
Tests that stop the documentation drifting away from the code.

CLAUDE.md already said "do not add a tool without updating docs/tool_catalog.md". That
rule was broken the first time somebody added a tool, which is what rules written only in
prose do. These tests turn the ones that are mechanically checkable into failures.

The scope is deliberately narrow: facts that a reader would act on and that the code
already knows the truth about. Prose is not checked, and nothing here is a style test.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

REPO = Path(__file__).resolve().parents[1]
TOOL_CATALOG = REPO / "docs" / "tool_catalog.md"
README = REPO / "README.md"
CLAUDE_MD = REPO / "CLAUDE.md"


def _bound_tools() -> set[str]:
    from tools import lc

    groups = (lc.RELIABILITY_TOOLS, lc.SUPPLY_CHAIN_TOOLS, lc.PRODUCTION_TOOLS,
              lc.QUALITY_TOOLS, lc.COMPLIANCE_TOOLS)
    return {t.name for group in groups for t in group}


def _catalog_text() -> str:
    return TOOL_CATALOG.read_text(encoding="utf-8")


# --- the tool catalog must cover what the agents can actually call ---------- #
def test_every_bound_tool_is_documented():
    """A tool an agent can call but that nobody documented is a tool nobody can review."""
    catalog = _catalog_text()
    missing = sorted(t for t in _bound_tools() if f"`{t}`" not in catalog)
    assert not missing, (
        f"these tools are bound to an agent but absent from docs/tool_catalog.md: {missing}. "
        "Add a section for each (see CLAUDE.md section 9)."
    )


def test_the_catalog_does_not_document_tools_that_no_longer_exist():
    """The other direction: a removed tool left in the catalog is a promise the system
    no longer keeps."""
    catalog = _catalog_text()
    documented = {m.group(1) for m in re.finditer(r"^### (?:\d+[a-z]?\. )?`([a-z_0-9]+)`",
                                                  catalog, re.MULTILINE)}
    stale = sorted(documented - _bound_tools())
    assert not stale, (
        f"docs/tool_catalog.md documents tools that are not bound to any agent: {stale}."
    )


def test_the_catalog_tool_count_matches_reality():
    catalog = _catalog_text()
    stated = re.search(r"(\d+) tools across", catalog)
    assert stated, "the tool catalog no longer states a tool count in its opening line"
    assert int(stated.group(1)) == len(_bound_tools()), (
        f"the catalog says {stated.group(1)} tools, the code binds {len(_bound_tools())}"
    )


def test_the_catalog_points_at_the_real_wrapper_module():
    """`tools_lc.py` has not existed since the tools became a package."""
    assert "tools_lc.py" not in _catalog_text(), (
        "docs/tool_catalog.md references tools_lc.py; the wrappers live in tools/lc.py"
    )


# --- headline numbers in the README must be the real ones ------------------ #
def test_readme_tool_count_is_correct():
    text = README.read_text(encoding="utf-8")
    stated = re.search(r"(\d+) domain tools", text)
    assert stated, "the README repository layout no longer states a tool count"
    assert int(stated.group(1)) == len(_bound_tools())


def test_readme_corpus_figures_match_the_corpus():
    from rag.index import corpus_stats

    stats = corpus_stats()
    text = README.read_text(encoding="utf-8")
    assert f"{stats['documents']} documents" in text, (
        f"the README corpus figure is stale: the corpus holds {stats['documents']} documents"
    )
    assert f"{stats['chunks']} section-level chunks" in text, (
        f"the README chunk figure is stale: the corpus holds {stats['chunks']} chunks"
    )


def test_readme_scenario_and_query_counts_match_the_datasets():
    from eval.scenarios import dataset_meta

    meta = dataset_meta()
    text = README.read_text(encoding="utf-8")
    assert f"**{meta['scenarios']}** labelled scenarios" in text, (
        f"the README says a different scenario count; the dataset holds {meta['scenarios']}"
    )
    assert f"{meta['rag_queries']} labelled queries" in text, (
        f"the README says a different query count; the dataset holds {meta['rag_queries']}"
    )


@pytest.mark.parametrize("doc", [README, CLAUDE_MD])
def test_docs_do_not_still_advertise_the_old_test_count(doc):
    """26 was the count before the offline suite grew. It appeared in four places and is
    the kind of number that silently becomes a lie."""
    text = doc.read_text(encoding="utf-8")
    assert "26 offline tests" not in text
    assert "26 tool tests" not in text


# --- the policy documented in CLAUDE.md must be the policy in code --------- #
def test_the_documented_spend_ceiling_is_the_enforced_one():
    import policy

    assert f"€{policy.COST_CEILING_EUR}" in CLAUDE_MD.read_text(encoding="utf-8"), (
        "CLAUDE.md section 5 states a different ceiling from policy.COST_CEILING_EUR"
    )
    assert f"{policy.COST_CEILING_EUR} EUR" in README.read_text(encoding="utf-8")


# Internal agent id -> the words the docs are allowed to call it. Checking the raw id
# would fail on prose that reads "Compliance and Safety", which is correct English and
# the right thing for a reader.
AGENT_PROSE = {
    "reliability": ["reliability"],
    "supply_chain": ["supply chain"],
    "production": ["production"],
    "quality": ["quality"],
    "compliance_safety": ["compliance and safety", "compliance & safety", "compliance_safety"],
}


def test_the_agent_roster_is_the_same_everywhere():
    from agents import AGENT_NAMES

    assert set(AGENT_NAMES) == set(AGENT_PROSE), (
        "the agent roster changed; update AGENT_PROSE in this test and the docs with it"
    )
    readme = README.read_text(encoding="utf-8").lower()
    catalog = _catalog_text().lower()
    for agent, spellings in AGENT_PROSE.items():
        assert any(s in readme for s in spellings), f"{agent} is missing from the README"
        assert any(s in catalog for s in spellings), f"{agent} is missing from the tool catalog"
    # The catalog is organised per challenge, so all five should appear in it.
    for challenge in range(1, 6):
        assert f"challenge {challenge}" in catalog
