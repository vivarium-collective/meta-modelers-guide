"""Fig 2 mechanistic variant — multirate orchestration (metabolism/biomass).

Separates MULTIRATE SCHEDULING (which clock fires when) from NUMERICAL ACCURACY
(convergence to a fine-step reference), and reports an honest input-output ledger
(biomass is only a yield-fraction of throughput; the pool+biomass sum is NOT
closed-system conservation). Gates carry the reviewer's evidence kind.
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
COMPOSITE = ROOT / "meta_modelers_guide" / "composites" / "fig02-mechanistic.composite.json"


def _spec(dt_fast=0.25, dt_slow=1.0, swap=False):
    spec = json.loads(COMPOSITE.read_text())
    spec["state"]["fast"]["interval"] = dt_fast
    spec["state"]["slow"]["interval"] = dt_slow
    if swap:  # reorder the process nodes in the state dict (fast/slow swapped)
        st = spec["state"]
        spec["state"] = {"slow": st["slow"], "fast": st["fast"],
                         "pool": st["pool"], "emitter": st["emitter"]}
    return spec


def _run(dt_fast=0.25, dt_slow=1.0, T=20, swap=False):
    spec = _spec(dt_fast, dt_slow, swap)
    sim = Composite({"state": spec["state"]}, core=build_core())
    sim.run(T)
    return gather_emitter_results(sim)[("emitter",)]


def test_composite_builds_and_runs():
    """REGRESSION_PIN: fig02-mechanistic builds and runs 20 time-units."""
    rows = _run()
    assert len(rows) >= 2 and float(rows[-1]["biomass"]) > 0


def test_input_output_ledger_closes_every_step():
    """INVARIANT: cumulative_input = ΔM + Δbiomass + Δwaste on every emitted row —
    an explicit input-output ledger. Nothing is created or lost unaccounted."""
    rows = _run()
    m0, b0, w0 = float(rows[0]["metabolite"]), float(rows[0]["biomass"]), float(rows[0]["waste"])
    worst = 0.0
    for r in rows:
        inp = float(r["cumulative_input"])
        d = (float(r["metabolite"]) - m0) + (float(r["biomass"]) - b0) + (float(r["waste"]) - w0)
        worst = max(worst, abs(inp - d))
    assert worst < 1e-9, f"ledger residual {worst:.2e}"


def test_pool_plus_biomass_is_not_closed_conservation():
    """INVARIANT (honest reframing): M + biomass is NOT the input budget — the waste
    sink (turnover + conversion loss) carries the balance. So the baseline's
    'molecules + biomass == time' is a cumulative-input artefact, not conservation."""
    rows = _run()
    last = rows[-1]
    m, b, w, inp = (float(last[k]) for k in ("metabolite", "biomass", "waste", "cumulative_input"))
    assert abs((m + b + w) - inp) < 1e-9        # the FULL budget closes
    assert (m + b) < 0.5 * inp                   # pool+biomass alone is far from the input
    assert w > 0                                 # mass genuinely leaves to waste


def test_euler_convergence_when_both_clocks_refined():
    """NUMERICAL_CONVERGENCE: refining the whole scheme (both clocks scaled together,
    Δt_fast=Δt_slow=Δt) converges to a fine reference. The convergence signal lives in
    the STIFF metabolite pool (its coarse-Δt overshoot), measured as the L1 trajectory
    error at integer times — it falls monotonically toward 0, ~O(Δt). (Refining only
    Δt_slow cannot beat the fast-clock floor — the multirate≠accuracy point below.)"""
    ref = _run(0.01, 0.01)
    grid = list(range(1, 21))
    m_ref = {t: _m_at(ref, t) for t in grid}

    def l1(dt):
        rows = _run(dt, dt)
        return sum(abs(_m_at(rows, t) - m_ref[t]) for t in grid)

    errs = [l1(dt) for dt in (1.0, 0.5, 0.25, 0.125, 0.0625)]
    assert all(errs[i + 1] < errs[i] for i in range(len(errs) - 1)), f"not converging: {errs}"
    assert errs[-1] < 0.05 * errs[0], "error not shrinking with Δt"


def _m_at(rows, t):
    """Metabolite at the emitted row nearest time t."""
    return float(min(rows, key=lambda r: abs(float(r["time"]) - t))["metabolite"])


def test_resolving_fast_clock_improves_pool_accuracy():
    """MECHANISTIC_ABLATION: multirate ≠ accuracy. The pool error lives in the stiff
    FAST transient — a coarse fast clock (r·Δt=1.5) overshoots, a fine fast clock
    tracks the reference. Measured at an early time (t≈2) where the transient is
    live; refining dt_fast cuts the error even at a fixed coarse dt_slow."""
    ref = _run(0.02, 0.02)
    m_ref = _m_at(ref, 2.0)
    coarse_fast = abs(_m_at(_run(1.0, 1.0), 2.0) - m_ref)
    fine_fast = abs(_m_at(_run(0.1, 1.0), 2.0) - m_ref)
    assert fine_fast < coarse_fast, f"fast clock should matter: fine {fine_fast:.3f} vs coarse {coarse_fast:.3f}"


def test_schedule_order_is_invariant():
    """INVARIANT: both processes read the pool at the tick boundary and return summed
    deltas, so coincident fast/slow updates are SYNCHRONOUS — swapping their order in
    the schedule leaves the trajectory identical (a well-posed scheduler, not an
    order-sensitive artefact)."""
    a = _run(swap=False)
    b = _run(swap=True)
    assert len(a) == len(b)
    for ra, rb in zip(a, b):
        for k in ("metabolite", "biomass", "waste"):
            assert abs(float(ra[k]) - float(rb[k])) < 1e-12


def test_no_mass_created_at_coincident_event_boundaries():
    """INVARIANT: at ticks where BOTH clocks fire (every integer time, dt_slow=1.0),
    the ledger still closes to machine precision — no mass is created or consumed at
    the event boundary where the two updates coincide."""
    rows = _run(dt_fast=0.25, dt_slow=1.0)
    m0, b0, w0 = float(rows[0]["metabolite"]), float(rows[0]["biomass"]), float(rows[0]["waste"])
    for r in rows:
        if abs(float(r["time"]) - round(float(r["time"]))) < 1e-9:  # coincident boundary
            inp = float(r["cumulative_input"])
            d = (float(r["metabolite"]) - m0) + (float(r["biomass"]) - b0) + (float(r["waste"]) - w0)
            assert abs(inp - d) < 1e-9


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
