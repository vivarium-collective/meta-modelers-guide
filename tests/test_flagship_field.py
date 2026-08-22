# tests/test_flagship_field.py
"""The flagship sense/act loop: over the run the cell depletes local glucose, grows
biomass + volume, secretes acetate into the field, and diffusion spreads it — a real
spatial realization of Fig 5 cell-environment coupling (niche construction).

Skipped when the optional ``cobra`` dependency is absent (CpmCellField requires it,
matching ``tests/test_cpm_cell_field.py``)."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import numpy as np
import pytest
from process_bigraph import Composite
from meta_modelers_guide.core import build_core

pytest.importorskip("cobra")  # entire module skips without COBRApy
pytest.importorskip("cpm")  # + the spatial frameworks (absent from base CI)
pytest.importorskip("spatio_flux")

_COMPOSITES = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"
COMP = _COMPOSITES / "single-cell-in-a-field.composite.json"
COMP_O2UNCAPPED = _COMPOSITES / "single-cell-in-a-field-o2uncapped.composite.json"
COMP_STEADYSTATE = _COMPOSITES / "single-cell-in-a-field-steadystate.composite.json"


def _run_acetate(comp_path):
    """Run a flagship-family composite for 20 ticks; return (field-wide acetate, obs)."""
    core = build_core()
    state = json.loads(comp_path.read_text())["state"]
    comp = Composite({"state": state}, core=core)
    comp.run(20)
    return float(np.asarray(comp.state["fields"]["acetate"]).sum()), comp.state["obs"]


def test_flagship_sense_act_loop():
    core = build_core()
    state = json.loads(COMP.read_text())["state"]
    comp = Composite({"state": state}, core=core)
    glc0 = float(np.asarray(comp.state["fields"]["glucose"]).sum())
    comp.run(20)
    obs = comp.state["obs"]
    assert obs["biomass"] > state["cell"]["config"]["biomass0"]   # metabolized
    assert obs["volume"] > 40.0                                    # grew
    assert float(np.asarray(comp.state["fields"]["acetate"]).sum()) > 0.0  # secreted
    assert float(np.asarray(comp.state["fields"]["glucose"]).sum()) < glc0  # consumed net


def test_o2_cap_is_what_forces_acetate_overflow():
    """Foundational mechanism control: the acetate the flagship secretes is *caused by*
    the O2 cap, not an artifact of the coupling. Lifting the oxygen bound
    (single-cell-in-a-field-o2uncapped, oxygen_vmax 2.5 -> 1000) lets unconstrained
    e_coli_core respire fully — pure aerobic respiration is growth-optimal, so EX_ac_e
    sits at 0 — and the cell secretes essentially no acetate, while the capped flagship
    secretes a clearly-positive plume. This turns the study's overflow claim from a code
    assertion into a demonstrated experiment."""
    capped_acetate, capped_obs = _run_acetate(COMP)
    uncapped_acetate, uncapped_obs = _run_acetate(COMP_O2UNCAPPED)

    # Capped flagship: a real, clearly-positive acetate plume.
    assert capped_acetate > 1.0
    # O2-uncapped control: full respiration -> ~0 acetate overflow.
    assert uncapped_acetate < 1e-6
    # And the mechanism, not merely the threshold: the cap makes a decisive difference.
    assert capped_acetate > 100.0 * max(uncapped_acetate, 1e-9)
    # The uncapped cell still metabolizes and grows (it just respires instead of
    # overflowing) — the control isolates the O2 cap, it doesn't break the cell.
    assert uncapped_obs["biomass"] > capped_obs["biomass"]


# ---------------------------------------------------------------------------
# M7d (peer review): two rigor checks on the flagship coupling.
# ---------------------------------------------------------------------------

def _run_cadence(interval, total=20.0):
    """Run the flagship at a given coupling cadence (sub-step the CpmCellField <-> dFBA
    <-> DiffusionAdvection loop at `interval`) and return the four gated observables plus
    the instantaneous local footprint glucose. Deterministic (fixed CPM seed)."""
    core = build_core()
    state = copy.deepcopy(json.loads(COMP.read_text())["state"])
    state["cell"]["interval"] = interval
    state["diff"]["interval"] = interval
    comp = Composite({"state": state}, core=core)
    glc0 = float(np.asarray(comp.state["fields"]["glucose"]).sum())
    comp.run(total)
    obs = comp.state["obs"]
    return {
        "biomass": float(obs["biomass"]),
        "volume": float(obs["volume"]),
        "acetate": float(np.asarray(comp.state["fields"]["acetate"]).sum()),
        "net_glucose_depleted": glc0 - float(np.asarray(comp.state["fields"]["glucose"]).sum()),
        "local_nutrient": float(obs["local_nutrient"]),
    }


def test_flagship_cadence_convergence():
    """M7d-cadence: the flagship's operator-split CPM<->dFBA<->diffusion loop runs at
    coupling cadence 1 today; only the PDE substeps are CFL-guarded. Halve then quarter
    the cadence and measure the drift in the four gated observables between the two finest
    levels (0.25 vs 0.5). Convergence band: <=10%.

    HONEST result: the three TIME-INTEGRATED observables (final biomass/volume, total
    acetate secreted, net glucose depleted) converge tightly (all <~3% between the finest
    two cadences) — those gated trajectories are cadence-robust. But the INSTANTANEOUS
    local-footprint glucose (obs.local_nutrient, the study's F-02 "~0.94 at t=20" pin and
    its derived ~18% peak-to-trough / ~6%-from-initial depletion figures) does NOT
    converge: it swings ~16% between cadences because it is a single-tick snapshot over a
    stochastically-shifting CPM footprint, and the CPM's fixed mcs_per_update is not
    interval-scaled (halving the cadence doubles the total Monte-Carlo relaxation the
    lattice receives). So the local-depletion pin is the one gated trajectory that moves
    under cadence refinement — a real finding, gated as a rigor caveat in study.yaml, not
    hidden."""
    fine = _run_cadence(0.25)
    mid = _run_cadence(0.5)

    def drift(key):
        return abs(fine[key] - mid[key]) / abs(mid[key])

    integrated = {k: drift(k) for k in ("biomass", "volume", "acetate", "net_glucose_depleted")}
    local_drift = drift("local_nutrient")

    # The three integrated gated observables converge within the 10% band.
    for k, d in integrated.items():
        assert d <= 0.10, f"integrated observable {k!r} drifted {d:.1%} (> 10% band)"

    # HONEST finding, pinned: the instantaneous local-footprint depletion does NOT
    # converge — it is the least-converged observable and exceeds the 10% band.
    assert local_drift > max(integrated.values()), (
        "expected local_nutrient to be the least-converged observable")
    assert local_drift > 0.10, (
        f"local_nutrient drift {local_drift:.1%} — the M7d finding is that this "
        "instantaneous footprint reading is NOT cadence-converged; if it has become "
        "converged, re-level F-02's cadence caveat in study.yaml")
    assert local_drift < 0.30, (
        f"local_nutrient drift {local_drift:.1%} unexpectedly large (> 30%) — "
        "investigate before trusting any local-footprint trajectory")


def test_steadystate_regime_reaches_flux_steady_state():
    """M7d-steady-state: the flagship is a pure transient (no source terms), so every
    flagship claim is a transient reading. single-cell-in-a-field-steadystate adds a
    first-order glucose SOURCE (grid-wide relaxation toward a setpoint), a first-order
    acetate DECAY sink, and a logistic biomass carrying capacity — turning the composite
    into a chemostat-like regime with a genuine flux fixed point. Run ~120 ticks it
    reaches a VERIFIED steady state.

    Criterion (declared): over the final 10 ticks, the max per-tick RELATIVE change of the
    biomass and of both field totals (glucose, acetate) is < 0.1%, i.e. d(biomass)/dt and
    the field fluxes have fallen below tolerance while the cell keeps metabolizing."""
    core = build_core()
    state = copy.deepcopy(json.loads(COMP_STEADYSTATE.read_text())["state"])
    comp = Composite({"state": state}, core=core)

    def snapshot():
        return (
            float(comp.state["obs"]["biomass"]),
            float(np.asarray(comp.state["fields"]["glucose"]).sum()),
            float(np.asarray(comp.state["fields"]["acetate"]).sum()),
        )

    tail = []
    for t in range(120):
        comp.run(1)
        if t >= 109:  # last 10 ticks
            tail.append(snapshot())

    # Max per-tick relative change over the final 10 ticks, per channel.
    def max_rate(idx):
        rates = [abs(tail[i][idx] - tail[i - 1][idx]) / abs(tail[i - 1][idx])
                 for i in range(1, len(tail)) if tail[i - 1][idx]]
        return max(rates)

    bio_rate, glc_rate, ace_rate = max_rate(0), max_rate(1), max_rate(2)
    assert bio_rate < 1e-3, f"biomass not at steady state: {bio_rate:.2%}/tick"
    assert glc_rate < 1e-3, f"field glucose not at steady state: {glc_rate:.2%}/tick"
    assert ace_rate < 1e-3, f"field acetate not at steady state: {ace_rate:.2%}/tick"

    # Steady-state values (loose pins; the point is that they are STANDING, not transient).
    bio, glc, ace = snapshot()
    obs = comp.state["obs"]
    assert 0.48 < bio < 0.50, f"steady-state biomass {bio}"            # -> B_cap 0.5
    assert 130.0 < obs["volume"] < 165.0, f"steady-state volume {obs['volume']}"
    assert 28.0 < ace < 35.0, f"steady-state field acetate {ace}"     # secretion == decay
    assert 5340.0 < glc < 5400.0, f"steady-state field glucose {glc}"  # uptake == source
    # The cell is still alive and metabolizing at steady state (not a dead/zeroed field).
    assert obs["biomass"] > state["cell"]["config"]["biomass0"]
