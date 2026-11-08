"""
The intelligence layer: one connected model of the operation that agents can reason over.

Each data file answers one question in isolation: what a machine needs, what is in stock,
who supplies a part, who supplies the supplier. The questions that matter cross them: "the
steel mill behind our bearing supplier has a furnace outage, which machines does that put
at risk, and what is a day of that worth?" This module builds a typed graph from the same
files the other tools read, so those questions become one call with a traceable path.

Nodes:  plant, machine, failure_mode, part, supplier, tier2_supplier, technician, cell, operator
Edges:  machine LOCATED_IN plant · machine HAS_FAILURE_MODE failure_mode
        failure_mode REQUIRES part · part STOCKED_AT plant · supplier SUPPLIES part
        supplier DEPENDS_ON tier2_supplier · machine EQUIVALENT_TO machine
        technician CAN_REPAIR failure_mode · cell SERVES machine · operator ASSIGNED_TO cell

Pure Python, no graph database: the point is the model, not the storage. Every result
carries the path that produced it, so an agent can cite how it got there.
"""
from __future__ import annotations

import json
from collections import defaultdict, deque
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"


def _load(rel: str) -> dict:
    return json.loads((DATA / rel).read_text(encoding="utf-8"))


class Graph:
    def __init__(self):
        self.nodes: dict[str, dict] = {}
        self.out: dict[str, list[tuple[str, str, dict]]] = defaultdict(list)
        self.inc: dict[str, list[tuple[str, str, dict]]] = defaultdict(list)

    def node(self, nid: str, kind: str, **attrs) -> str:
        cur = self.nodes.setdefault(nid, {"id": nid, "kind": kind})
        cur.update({k: v for k, v in attrs.items() if v is not None})
        return nid

    def edge(self, a: str, rel: str, b: str, **attrs) -> None:
        if any(r == rel and t == b for r, t, _ in self.out[a]):
            return
        self.out[a].append((rel, b, attrs))
        self.inc[b].append((rel, a, attrs))

    def kind(self, nid: str) -> str:
        return self.nodes.get(nid, {}).get("kind", "")

    def stats(self) -> dict:
        kinds = defaultdict(int)
        for n in self.nodes.values():
            kinds[n["kind"]] += 1
        return {"nodes": len(self.nodes), "edges": sum(len(v) for v in self.out.values()), "by_kind": dict(kinds)}


@lru_cache(maxsize=1)
def build() -> Graph:
    g = Graph()
    assets = _load("assets/asset_profiles.json")
    for mid, a in assets.items():
        if not isinstance(a, dict) or "plant_id" not in a:
            continue
        g.node(a["plant_id"], "plant", name=a.get("plant_name"))
        g.node(mid, "machine", name=a.get("name"), value_per_day_eur=a.get("production_value_per_day_eur"))
        g.edge(mid, "LOCATED_IN", a["plant_id"])
        for eq in a.get("equivalent_machines", []):
            g.node(eq, "machine")
            g.edge(mid, "EQUIVALENT_TO", eq)
        for fm, f in (a.get("failure_modes") or {}).items():
            fid = g.node(f"{mid}:{fm}", "failure_mode", name=fm.replace("_", " "), repair_hours=f.get("estimated_repair_hours"))
            g.edge(mid, "HAS_FAILURE_MODE", fid)
            for b in f.get("bom", []):
                g.node(b["part_id"], "part", name=b.get("description"))
                g.edge(fid, "REQUIRES", b["part_id"], qty=b.get("qty_required"))
            for t in f.get("available_technicians", []):
                g.node(f"tech:{t}", "technician", name=t)
                g.edge(f"tech:{t}", "CAN_REPAIR", fid)

    stock = _load("inventory/parts_stock.json")
    for pid, p in stock.items():
        if not pid.startswith("P-"):
            continue
        g.node(pid, "part", name=p.get("description"))
        for plant, s in (p.get("plants") or {}).items():
            g.node(plant, "plant")
            g.edge(pid, "STOCKED_AT", plant, qty=s.get("qty"))
        wh = p.get("warehouse") or {}
        if wh.get("location"):
            g.node(f"wh:{wh['location']}", "warehouse", name=wh.get("location_name"))
            g.edge(pid, "STOCKED_AT", f"wh:{wh['location']}", qty=wh.get("qty"), transit_hours=wh.get("transit_hours_standard"))

    catalog = _load("suppliers/supplier_catalog.json")
    for pid, p in catalog.items():
        if not pid.startswith("P-"):
            continue
        for s in p.get("suppliers", []):
            g.node(s["supplier_id"], "supplier", name=s.get("name"), location=s.get("location"))
            g.edge(s["supplier_id"], "SUPPLIES", pid, lead_time_hours=s.get("standard_lead_time_hours"),
                   unit_price_eur=s.get("standard_unit_price_eur"), reliability=s.get("reliability_score"))

    tier2 = _load("suppliers/tier2_map.json")
    for sid, s in tier2.items():
        if not sid.startswith("SUP-"):
            continue
        g.node(sid, "supplier", name=s.get("tier1_name"))
        for d in s.get("tier2_dependencies", []):
            g.node(d["tier2_id"], "tier2_supplier", name=d.get("name"), material=d.get("material"))
            g.edge(sid, "DEPENDS_ON", d["tier2_id"], risk=d.get("risk_flag"), single_source=d.get("single_source"),
                   note=d.get("risk_note"))

    cells = _load("production/robot_cells.json")
    for c in cells.get("cells", []):
        g.node(c["cell_id"], "cell", mode=c.get("mode"), safety_state=c.get("safety_state"))
        g.edge(c["cell_id"], "SERVES", c["serves_machine"])
        for op in c.get("operators_assigned", []):
            g.node(f"op:{op}", "operator", name=op)
            g.edge(f"op:{op}", "ASSIGNED_TO", c["cell_id"])
    return g


def _label(g: Graph, nid: str) -> str:
    n = g.nodes.get(nid, {})
    return f"{n.get('name') or nid} ({n.get('kind', '?')})" if n.get("name") and n.get("name") != nid else nid


def _resolve(g: Graph, ref: str) -> str | None:
    """Accept an id, a prefixed id, or a name fragment."""
    if ref in g.nodes:
        return ref
    for p in ("tech:", "op:", "wh:"):
        if p + ref in g.nodes:
            return p + ref
    low = ref.lower()
    hits = [nid for nid, n in g.nodes.items() if low in str(n.get("name", "")).lower() or low in nid.lower()]
    return hits[0] if len(hits) == 1 else (min(hits, key=len) if hits else None)


def supplier_impact(supplier_id: str) -> dict:
    """Everything downstream of a supplier (Tier-1 or Tier-2): parts, failure modes,
    machines, plants, the production value exposed per day, and whether each part has
    another source."""
    g = build()
    sid = _resolve(g, supplier_id)
    if not sid or g.kind(sid) not in ("supplier", "tier2_supplier"):
        return {"error": f"unknown supplier {supplier_id!r}", "known": sorted(n for n in g.nodes if g.kind(n) in ("supplier", "tier2_supplier"))}
    tier1 = [a for rel, a, _ in g.inc[sid] if rel == "DEPENDS_ON"] if g.kind(sid) == "tier2_supplier" else [sid]
    parts = sorted({p for t in tier1 for rel, p, _ in g.out[t] if rel == "SUPPLIES"})
    machines, modes, paths = set(), set(), []
    for p in parts:
        for rel, fm, _ in g.inc[p]:
            if rel != "REQUIRES":
                continue
            modes.add(fm)
            m = next(a for r, a, _ in g.inc[fm] if r == "HAS_FAILURE_MODE")
            machines.add(m)
            chain = ([sid] if sid not in tier1 else []) + [t for t in tier1 if p in {x for r, x, _ in g.out[t] if r == "SUPPLIES"}][:1] + [p, fm, m]
            paths.append(" -> ".join(_label(g, x) for x in chain))
    alternatives = {p: sorted(s for r, s, _ in g.inc[p] if r == "SUPPLIES" and s not in tier1) for p in parts}
    plants = sorted({x for m in machines for r, x, _ in g.out[m] if r == "LOCATED_IN"})
    value = sum(g.nodes[m].get("value_per_day_eur") or 0 for m in machines)
    risk = [{"tier1": a, **attrs} for rel, a, attrs in g.inc[sid] if rel == "DEPENDS_ON"] if g.kind(sid) == "tier2_supplier" else \
           [{"tier2": b, **attrs} for rel, b, attrs in g.out[sid] if rel == "DEPENDS_ON"]
    return {"supplier": _label(g, sid), "via_tier1": tier1 if sid not in tier1 else [], "parts": parts,
            "failure_modes": sorted(modes), "machines": sorted(machines), "plants": plants,
            "production_value_exposed_per_day_eur": value, "parts_without_another_source": sorted(p for p, a in alternatives.items() if not a),
            "alternative_suppliers": alternatives, "risk_flags": risk, "paths": sorted(set(paths))}


def machine_dependencies(machine_id: str) -> dict:
    """What one machine depends on: parts per failure mode with stock and suppliers (and
    their Tier-2 risk), technicians, the robot cell and its operators, equivalent machines."""
    g = build()
    mid = _resolve(g, machine_id)
    if not mid or g.kind(mid) != "machine":
        return {"error": f"unknown machine {machine_id!r}", "known": sorted(n for n in g.nodes if g.kind(n) == "machine")}
    modes = []
    for rel, fm, _ in g.out[mid]:
        if rel != "HAS_FAILURE_MODE":
            continue
        parts = []
        for r, p, a in g.out[fm]:
            if r != "REQUIRES":
                continue
            stock = {x: at.get("qty") for rr, x, at in g.out[p] if rr == "STOCKED_AT"}
            sups = []
            for rr, s, sa in g.inc[p]:
                if rr == "SUPPLIES":
                    t2 = [{"tier2": t, "risk": ta.get("risk"), "single_source": ta.get("single_source")} for r3, t, ta in g.out[s] if r3 == "DEPENDS_ON"]
                    sups.append({"supplier": s, "lead_time_hours": sa.get("lead_time_hours"), "tier2": t2})
            parts.append({"part": p, "qty_required": a.get("qty"), "stock": stock, "suppliers": sups})
        techs = sorted(a.replace("tech:", "") for r, a, _ in g.inc[fm] if r == "CAN_REPAIR")
        modes.append({"failure_mode": g.nodes[fm]["name"], "parts": parts, "technicians": techs})
    cells = [c for r, c, _ in g.inc[mid] if r == "SERVES"]
    ops = sorted({o.replace("op:", "") for c in cells for r, o, _ in g.inc[c] if r == "ASSIGNED_TO"})
    return {"machine": _label(g, mid), "plant": next((p for r, p, _ in g.out[mid] if r == "LOCATED_IN"), None),
            "value_per_day_eur": g.nodes[mid].get("value_per_day_eur"), "failure_modes": modes,
            "cells": cells, "operators": ops, "equivalent_machines": sorted(e for r, e, _ in g.out[mid] if r == "EQUIVALENT_TO")}


HUBS = {"plant", "warehouse"}


def trace_dependency(source: str, target: str) -> dict:
    """The shortest chain of relationships linking two things in the operation, e.g. a
    Tier-2 steel mill and a machine. Walks edges in both directions."""
    g = build()
    a, b = _resolve(g, source), _resolve(g, target)
    if not a or not b:
        return {"error": f"unknown {'source' if not a else 'target'}: {source if not a else target!r}"}
    prev, q = {a: None}, deque([a])
    while q:
        n = q.popleft()
        if n == b:
            break
        # Plants and warehouses are places, not dependencies: sharing one is not a causal link.
        if n != a and g.kind(n) in HUBS:
            continue
        for rel, x, _ in g.out[n]:
            if x not in prev:
                prev[x] = (n, rel, "->")
                q.append(x)
        for rel, x, _ in g.inc[n]:
            if x not in prev:
                prev[x] = (n, rel, "<-")
                q.append(x)
    if b not in prev:
        return {"source": a, "target": b, "connected": False}
    steps, n = [], b
    while prev[n]:
        p, rel, d = prev[n]
        steps.append(f"{_label(g, p)} -[{rel}]-> {_label(g, n)}" if d == "->" else f"{_label(g, n)} -[{rel}]-> {_label(g, p)}")
        n = p
    return {"source": a, "target": b, "connected": True, "hops": len(steps), "path": list(reversed(steps))}


def single_points_of_failure() -> dict:
    """Weak spots: parts with too little stock at the plant that needs them and one supplier;
    single-source Tier-2 dependencies; operators assigned to more than one cell."""
    g = build()
    parts = []
    for p in (n for n in g.nodes if g.kind(n) == "part"):
        sups = [s for r, s, _ in g.inc[p] if r == "SUPPLIES"]
        for r, fm, need in g.inc[p]:
            if r != "REQUIRES":
                continue
            m = next(a for rr, a, _ in g.inc[fm] if rr == "HAS_FAILURE_MODE")
            plant = next((x for rr, x, _ in g.out[m] if rr == "LOCATED_IN"), None)
            on_site = next((at.get("qty") for rr, x, at in g.out[p] if rr == "STOCKED_AT" and x == plant), 0) or 0
            required = need.get("qty") or 1
            if on_site < required and len(sups) <= 1:
                parts.append({"part": p, "machine": m, "plant": plant, "on_site": on_site, "required": required, "suppliers": sups})
    t2 = [{"tier1": s, "tier2": t, "risk": a.get("risk")} for s in g.nodes if g.kind(s) == "supplier"
          for r, t, a in g.out[s] if r == "DEPENDS_ON" and a.get("single_source")]
    ops = []
    for o in (n for n in g.nodes if g.kind(n) == "operator"):
        cells = [c for r, c, _ in g.out[o] if r == "ASSIGNED_TO"]
        if len(cells) > 1:
            ops.append({"operator": o.replace("op:", ""), "cells": cells})
    return {"parts_short_on_site_with_one_supplier": parts, "single_source_tier2": t2,
            "operators_on_several_cells": ops, "graph": g.stats()}
