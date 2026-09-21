import json
from pathlib import Path

from .runtime_inputs import current

DATA_DIR = Path(__file__).parent.parent / "data" / "suppliers"


def supplier_catalog(part_ids: list[str], scenario: str = "default") -> dict:
    """
    Returns supplier options, lead times, and expedite availability for part IDs.

    Tool catalog:
      Input:  part_ids (list of part IDs), scenario ("default" | "edge")
      Output: per-part: suppliers list with standard/expedite lead time + cost premium
      Use when: on-site stock insufficient, need to source from external supplier
      Do NOT use: before confirming stock gap via parts_inventory
      Fallback: if catalog stale (>24h), flag and present last known with caveat
      Risk tier: READ (autonomous)

    scenario="edge" loads supplier_catalog_edge.json — a real disruption snapshot in
    which no external supplier or warehouse transfer fits the failure window, forcing
    the agent to adapt (cross-plant transfer). Same schema, different data.
    """
    sourcing = current().get("sourcing")
    if sourcing is not None:
        return {"parts": {p: {"source": "labelled scenario"} for p in part_ids},
                "combined_options": sourcing.get("options", []),
                "scenario_note": "Use these scenario quotes; do not substitute demo quotes."}
    filename = "supplier_catalog_edge.json" if scenario == "edge" else "supplier_catalog.json"
    catalog_file = DATA_DIR / filename
    if not catalog_file.exists():
        return {"error": "catalog_unavailable"}

    with open(catalog_file, encoding="utf-8") as f:
        catalog = json.load(f)

    results = {}
    for part_id in part_ids:
        part_data = catalog.get(part_id)
        if not part_data:
            results[part_id] = {"error": "part_not_in_catalog"}
            continue
        results[part_id] = part_data

    return {
        "parts": results,
        "combined_options": catalog.get("combined_options", {}),
        "catalog_timestamp": catalog.get("catalog_timestamp"),
        "scenario_note": catalog.get("scenario_note"),
    }
