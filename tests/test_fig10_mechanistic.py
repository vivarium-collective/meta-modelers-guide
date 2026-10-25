"""Fig 10 mechanistic variant — spatially-emergent biofilm (fig10-mechanistic,
BiofilmColony). Attachment EMERGES from cluster geometry, not a wall clock; ECM
binds the community; matched-null controls isolate each arm.

Each gate carries the reviewer's evidence class (pass_if.kind). Matched-null
controls use an EPSILON, never 0.0 (a float 0.0 config is restored to the schema
default). See reference_matched_null_controls_need_epsilon.
"""
from __future__ import annotations

import copy
import json
import math
import warnings
from pathlib import Path

import pytest
from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
COMPOSITE = ROOT / "meta_modelers_guide" / "composites" / "fig10-mechanistic.composite.json"
N = 6
EPS = 1e-9


def _base():
    return json.loads(COMPOSITE.read_text())


def _ring(spec, radius, cx=8.0, cy=8.0):
    """Replace the initial cell positions with a ring of the given radius."""
    xs = {"_type": "map", "_value": "float"}
    ys = {"_type": "map", "_value": "float"}
    for i in range(N):
        a = 2 * math.pi * i / N
        xs[str(i)] = cx + radius * math.cos(a)
        ys[str(i)] = cy + radius * math.sin(a)
    spec["state"]["xs"] = xs
    spec["state"]["ys"] = ys


def _run(cfg_over=None, ring=None, steps=None):
    spec = _base()
    if cfg_over:
        spec["state"]["colony_dynamics"]["config"].update(cfg_over)
    if ring is not None:
        _ring(spec, ring)
    sim = Composite({"state": spec["state"]}, core=build_core())
    sim.run(steps or spec["default_n_steps"])
    return gather_emitter_results(sim)[("emitter",)]


def _formation_time(rows):
    f = [int(float(r["formed"])) for r in rows]
    return next((i for i, x in enumerate(f) if x == 1), None)


def _nested_cells(colony):
    bf = colony.get("biofilm") if isinstance(colony, dict) else None
    if not isinstance(bf, dict):
        return {}
    return {k: v for k, v in bf.get("contents", {}).items() if not str(k).startswith("_")}


# ── structural / invariant ────────────────────────────────────────────────────

def test_composite_builds_and_runs():
    """REGRESSION_PIN: fig10-mechanistic builds and runs 24 ticks (25 rows)."""
    assert len(_run()) == 25


def test_cell_identity_and_biomass_preserved_on_reparenting():
    """INVARIANT: the place-graph rewrite that nests the cells under the biofilm node
    preserves BOTH cell count and per-cell biomass — reparenting is a pure topology
    move, it neither creates nor destroys cells or mass."""
    rows = _run()
    nested = _nested_cells(rows[-1]["colony"])
    assert len(nested) == N, "cell count not preserved on reparenting"
    assert all(abs(v["contents"]["biomass"] - 1.0) < 1e-12 for v in nested.values()), \
        "per-cell biomass not preserved on reparenting"


# ── emergent formation (not a wall clock) ────────────────────────────────────

def test_formation_is_emergent_not_clocked():
    """PROSPECTIVE_PREDICTION: formation is triggered by the cluster geometry, so its
    timing MUST depend on how fast the cells aggregate — stronger adhesion forms
    earlier, weaker later. A wall-clock trigger (the baseline) would fire at the same
    tick regardless. Prediction: t(form) strictly decreases as adhesion increases."""
    t_slow = _formation_time(_run(cfg_over={"adhesion": 0.25}))
    t_mid = _formation_time(_run(cfg_over={"adhesion": 0.35}))
    t_fast = _formation_time(_run(cfg_over={"adhesion": 0.55}))
    assert None not in (t_slow, t_mid, t_fast), "biofilm failed to form under adhesion"
    assert t_slow > t_mid > t_fast, f"formation time not adhesion-dependent: {t_slow},{t_mid},{t_fast}"


def test_density_hastens_formation():
    """EMPIRICAL_COMPARISON (quorum/density dependence): a denser initial cluster
    (smaller ring) reaches quorum proximity sooner, so it forms earlier; a cluster
    spread beyond the sensing radius never coordinates and does not form."""
    t_dense = _formation_time(_run(ring=2.5))
    t_loose = _formation_time(_run(ring=4.2))
    assert t_dense is not None and t_loose is not None
    assert t_dense < t_loose, "denser cluster should form sooner"
    # spread beyond sensing radius: no aggregation, no biofilm
    assert _formation_time(_run(ring=9.0, cfg_over={"sense_radius": 6.0})) is None


# ── matched-null controls: each arm ──────────────────────────────────────────

def test_no_adhesion_prevents_stable_aggregate():
    """MECHANISTIC_ABLATION (adhesion off, ε): without local adhesion the cells never
    aggregate — the cluster radius stays near its initial spread and no biofilm forms."""
    rows = _run(cfg_over={"adhesion": EPS})
    assert _formation_time(rows) is None, "biofilm formed without adhesion"
    cr = [float(r["cluster_radius"]) for r in rows[1:]]
    assert min(cr) > 3.5, "cluster contracted without adhesion"
    assert _nested_cells(rows[-1]["colony"]) == {}, "cells nested without aggregating"


def test_blocked_ecm_changes_persistence_and_morphology():
    """MECHANISTIC_ABLATION (ECM off, ε): the cells still aggregate and form, but
    without matrix the community does not persist — the sessile cells spread back
    apart, so the final cluster is far larger (and cohesion stays ~0) than with ECM."""
    full = _run()
    no_ecm = _run(cfg_over={"ecm_rate": EPS})
    assert _formation_time(no_ecm) is not None, "no-ECM run should still form"
    r_full = float(full[-1]["cluster_radius"])
    r_noecm = float(no_ecm[-1]["cluster_radius"])
    assert r_noecm > r_full + 3.0, "blocked ECM did not disperse the community"
    assert float(full[-1]["cohesion"]) > 0.5 and float(no_ecm[-1]["cohesion"]) < 0.1


def test_collective_port_operative_only_after_organization():
    """MECHANISTIC_ABLATION: the collective-level observables (cohesion, the biofilm
    node) are inert BEFORE the community organizes and become operative only AFTER.
    cohesion is exactly 0 pre-formation and positive post-formation; the biofilm node
    is absent before and present after."""
    rows = _run()
    ft = _formation_time(rows)
    assert ft is not None
    assert all(float(rows[i]["cohesion"]) == 0.0 for i in range(ft)), "cohesion live before organization"
    assert float(rows[-1]["cohesion"]) > 0.5, "cohesion not operative after organization"
    assert "biofilm" not in (rows[ft - 1]["colony"] or {}), "biofilm node existed before formation"
    assert "biofilm" in rows[-1]["colony"], "biofilm node missing after formation"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
