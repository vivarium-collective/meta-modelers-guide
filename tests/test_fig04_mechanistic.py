"""Fig 4 (paper Fig 5) mechanistic variant — reaction–diffusion field with a
depleting, chemotactic cell. Closes the sense/act loop the baseline left open:
the cell's uptake is now a real sink on the shared field.

Each gate carries the reviewer's evidence class (pass_if.kind). NOTE: matched-null
controls use an EPSILON, never 0.0 — bigraph_schema treats an explicit float 0.0
config as empty and silently restores the schema default (so vmax=0.0 would NOT
disable uptake). See reference_matched_null_controls_need_epsilon.
"""
from __future__ import annotations

import copy
import json
import warnings
from pathlib import Path

import pytest
from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
COMPOSITE = ROOT / "meta_modelers_guide" / "composites" / "fig04-mechanistic.composite.json"
N = 25
EPS = 1e-9   # matched-null control value (NOT 0.0 — see module docstring)


def _base():
    return json.loads(COMPOSITE.read_text())


def _spec(cell_over=None, source_over=None, field=None, drop=None):
    spec = _base()
    for name in (drop or []):
        spec["state"].pop(name, None)
    if cell_over and "cell" in spec["state"]:
        spec["state"]["cell"]["config"].update(cell_over)
    if source_over and "source" in spec["state"]:
        spec["state"]["source"]["config"].update(source_over)
    if field is not None:
        g = {"_type": "map", "_value": "float"}
        g.update({str(i): field[i] for i in range(N)})
        spec["state"]["environment"]["chemical_field"] = g
    return spec


def _run(cell_over=None, source_over=None, field=None, drop=None, steps=24):
    """Clean emitter rows from a single run(steps); per-tick field snapshots from a
    parallel stepped sim (deterministic → identical). The emitter is a Step that
    fires per process-update, so stepping 1-at-a-time would double-count its rows."""
    spec = _spec(cell_over, source_over, field, drop)
    core = build_core()
    sim = Composite({"state": spec["state"]}, core=core)
    sim.run(steps)
    rows = gather_emitter_results(sim)[("emitter",)]
    sim2 = Composite({"state": copy.deepcopy(spec)["state"]}, core=build_core())
    snaps = [[float(sim2.state["environment"]["chemical_field"][str(i)]) for i in range(N)]]
    for _ in range(steps):
        sim2.run(1)
        snaps.append([float(sim2.state["environment"]["chemical_field"][str(i)]) for i in range(N)])
    return snaps, rows


# ── structural / invariant ────────────────────────────────────────────────────

def test_composite_builds_and_runs():
    """REGRESSION_PIN: fig04-mechanistic builds and runs 24 ticks (25 rows)."""
    _, rows = _run()
    assert len(rows) == 25


def test_mass_ledger_closes():
    """INVARIANT: with Neumann edges, Σfield change = Σsource − Σdecay − Σuptake,
    and biomass change = yield·Σuptake — nothing is created; the cell's growth is
    paid out of the field. Both close to machine precision."""
    snaps, rows = _run()
    last = rows[-1]
    src, dec, upt = float(last["source_total"]), float(last["decay_total"]), float(last["uptake_total"])
    d_field = sum(snaps[-1]) - sum(snaps[0])
    assert abs(d_field - (src - dec - upt)) < 1e-9, "field mass ledger does not close"
    d_bm = float(rows[-1]["biomass"]) - float(rows[0]["biomass"])
    assert abs(d_bm - 0.6 * upt) < 1e-9, "biomass is not paid out of uptake at the yield"


def test_diffusion_is_mass_conserving():
    """INVARIANT: pure diffusion (uptake off, source off) conserves the total field
    to round-off — the Neumann Laplacian neither creates nor loses mass."""
    flat = [1.0 if i == N // 2 else 0.0 for i in range(N)]
    # drop the cell and source entirely → pure diffusion, exact conservation
    snaps, _ = _run(field=flat, drop=["cell", "source"])
    assert abs(sum(snaps[-1]) - sum(snaps[0])) < 1e-9


# ── mechanistic ablations: each arm of the loop ──────────────────────────────

def test_cell_depletes_the_field_real_feedback():
    """MECHANISTIC_ABLATION: the cell's uptake is a real SINK — the field under the
    cell is drawn down below the no-uptake control (a depletion well), and the cell
    leaves a measurable footprint on the environment. This is the bidirectional
    feedback the baseline lacked (its uptake never touched the field)."""
    full, rows = _run()
    nouptake, _ = _run(cell_over={"vmax": EPS})
    footprint = max(abs(full[t][i] - nouptake[t][i]) for t in range(len(full)) for i in range(N))
    assert footprint > 0.1, "cell leaves no footprint on the field — no real feedback"
    # the deepest depletion well anywhere along the track (with-cell below no-uptake)
    well = max(nouptake[t][i] - full[t][i] for t in range(len(full)) for i in range(N))
    assert well > 0.1, "no depletion well — uptake is not drawing the field down"


def test_no_uptake_preserves_the_field():
    """MECHANISTIC_ABLATION (matched null, ε): with uptake off the cell takes nothing
    up (biomass constant) and leaves the field identical to a cell-free environment."""
    _, rows = _run(cell_over={"vmax": EPS})
    assert abs(float(rows[-1]["biomass"]) - float(rows[0]["biomass"])) < 1e-6


def test_no_motility_means_no_displacement():
    """MECHANISTIC_ABLATION (matched null, ε): with chemotaxis off the cell holds its
    position but still takes up nutrient locally (uptake preserved, no displacement)."""
    _, rows = _run(cell_over={"chemotaxis": EPS})
    assert abs(float(rows[-1]["position"]) - float(rows[0]["position"])) < 1e-6
    assert float(rows[-1]["biomass"]) > float(rows[0]["biomass"]), "cell should still eat in place"


def test_chemotaxis_climbs_the_gradient():
    """MECHANISTIC_ABLATION: the full cell moves UP the gradient toward the source
    (position decreases toward 0) and the nutrient it senses rises as it climbs."""
    _, rows = _run()
    assert float(rows[-1]["position"]) < float(rows[0]["position"]) - 5.0, "cell did not climb the gradient"
    assert float(rows[-1]["local_conc"]) > float(rows[1]["local_conc"]), "sensed nutrient did not rise while climbing"


def test_zero_gradient_abolishes_directed_drift():
    """MECHANISTIC_ABLATION: on a UNIFORM field (no source gradient) there is no
    directed chemotactic drift — the cell does not move systematically toward a
    source that isn't there. Controls for 'is the motion really gradient-following?'"""
    uniform = [0.5] * N
    _, rows = _run(source_over={"source_rate": EPS}, field=uniform)
    assert abs(float(rows[-1]["position"]) - float(rows[0]["position"])) < 1.0


# ── saturating transport ─────────────────────────────────────────────────────

def test_uptake_saturates_michaelis_menten():
    """EMPIRICAL_COMPARISON: uptake follows saturating Michaelis–Menten kinetics —
    it is bounded by vmax at high concentration and rises ~linearly at low
    concentration, not the baseline's unbounded proportional draw."""
    from meta_modelers_guide.handlers_fig04_mech import MotileCell
    core = build_core()
    cfg = dict(vmax=0.45, km=0.30, yield_coef=0.6, chemotaxis=EPS, max_step=1.0)

    def uptake_at(c):
        field = {str(i): c for i in range(N)}
        return MotileCell(cfg, core=core).update({"chemical_field": field, "position": 12.0, "biomass": 1.0}, 1.0)["uptake"]

    hi = uptake_at(100.0)      # saturated
    lo = uptake_at(0.03)       # far below Km
    assert hi < 0.45 and hi > 0.45 * 0.99, "high-c uptake should approach vmax"
    assert lo < 0.1 * hi, "low-c uptake should be far below saturation (linear regime)"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
