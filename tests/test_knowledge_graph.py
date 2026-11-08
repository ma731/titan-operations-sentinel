"""The knowledge graph: built from the same data files, answers cross-file questions with a path."""
from tools import knowledge_graph as kg


def test_graph_is_built_from_every_data_source():
    s = kg.build().stats()["by_kind"]
    for kind in ("plant", "machine", "failure_mode", "part", "supplier", "tier2_supplier", "technician", "cell", "operator"):
        assert s.get(kind, 0) >= 1, kind


def test_tier2_outage_reaches_the_machine_through_its_tier1():
    r = kg.supplier_impact("T2-OVAKO-SE")
    assert r["via_tier1"] == ["SUP-SCHAEFFLER-DE"]
    assert "CNC-07-LEI" in r["machines"] and r["plants"] == ["LEI"]
    assert r["production_value_exposed_per_day_eur"] == 180000
    assert "P-7803" in r["parts_without_another_source"]          # only Schaeffler lists the seal set
    assert "P-4421" not in r["parts_without_another_source"]      # SKF also supplies the bearing kit


def test_names_resolve_as_well_as_ids():
    assert kg.supplier_impact("Ovako")["via_tier1"] == ["SUP-SCHAEFFLER-DE"]
    assert "error" in kg.supplier_impact("Nobody GmbH")


def test_trace_follows_dependencies_not_shared_sites():
    r = kg.trace_dependency("Ovako", "CNC-07-LEI")
    assert r["connected"] and r["hops"] == 4
    path = " ".join(r["path"])
    assert "SUPPLIES" in path and "REQUIRES" in path and "HAS_FAILURE_MODE" in path
    assert "LOCATED_IN" not in path and "STOCKED_AT" not in path


def test_machine_dependencies_carry_stock_suppliers_and_tier2_risk():
    d = kg.machine_dependencies("CNC-07-LEI")
    bearing = next(f for f in d["failure_modes"] if f["failure_mode"] == "spindle bearing failure")
    kit = next(p for p in bearing["parts"] if p["part"] == "P-4421")
    assert kit["stock"]["LEI"] == 0 and kit["stock"]["wh:AMS"] == 3
    assert any(t["risk"] == "ELEVATED" for s in kit["suppliers"] for t in s["tier2"])
    assert set(bearing["technicians"]) == {"Müller", "Becker"}
    assert d["equivalent_machines"] == ["CNC-05-LEI", "CNC-08-LEI"]


def test_single_points_of_failure():
    w = kg.single_points_of_failure()
    seal = [p for p in w["parts_short_on_site_with_one_supplier"] if p["part"] == "P-7803"]
    assert seal and seal[0]["on_site"] == 1 and seal[0]["required"] == 2
    assert any(t["tier2"] == "T2-OVAKO-SE" for t in w["single_source_tier2"])
    assert any(o["operator"] == "op_Keller" for o in w["operators_on_several_cells"])


def test_supply_chain_agent_can_call_the_graph():
    from tools import lc
    names = {t.name for t in lc.SUPPLY_CHAIN_TOOLS}
    assert {"supplier_impact", "trace_dependency"} <= names
