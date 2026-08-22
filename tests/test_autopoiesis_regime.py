"""Study 7 (`autopoiesis`) demonstrating claim, locked as a regression test:
the closed autopoietic loop (`protocell-autopoietic`, `k_prod=0.03`) PERSISTS
-- homeostasis, mass-held gate, not a filled blob -- while the negative
control (`protocell-vesicle-control`, `k_prod=0.0`) COLLAPSES, and this
contrast is robust across seeds.

Both composites are run directly from their JSON specs in
`meta_modelers_guide/composites/` (not hand-built state), so this test is
also a regression guard on the composite files themselves.

**Window (Task-1 ruling, carried forward):** the closed-loop homeostatic
plateau is METASTABLE, not perpetual -- it self-maintains through ~2000
internal steps but eventually runs down past ~2450-2650 steps even with
production on. Both composites pin `steps_per_tick=50`, so this module caps
the closed-loop run at 36 ticks (1800 internal steps) -- the same margin
`tests/test_protocell.py::test_closed_loop_persists_within_stable_window`
already validates -- deliberately short of the breakdown range so the test
can never flake into catching the eventual collapse.

**Multi-seed finding (honest, not the convention's usual result):** unlike
the CPM/Metropolis processes `tests/test_cellcell_multiseed.py` established
this convention for, `Protocell`'s reaction-diffusion physics
(`meta_modelers_guide/protocell/autopoiesis.py::rd_step`) has NO RNG --
`seed` is accepted in the config schema but is currently inert (see that
module's docstring). Varying it here is still the correct thing to do (it
is the documented interface for a future stochastic variant, and this test
is the regression guard that would catch it silently starting to matter),
but today it produces an EXACT, not merely tolerant, invariant: every seed
1-5 gives identical enclosed_area. Observed:
    closed loop (`protocell-autopoietic`, 36 ticks): enclosed_area == 149.0
        at every seed in 1-5 (persists == 1.0 every seed)
    control (`protocell-vesicle-control`, 6 ticks): enclosed_area == 0.0
        at every seed in 1-5 (persists == 0.0, collapse_tick == 96.0 every seed)
The range assertions below use loose bounds (not the exact observed point)
so the test does not silently become a golden-value pin if/when `seed`
starts actually driving stochastic noise in this process.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

pytest.importorskip("process_bigraph")

from process_bigraph import Composite  # noqa: E402
from meta_modelers_guide.core import build_core  # noqa: E402

COMPOSITES = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"
SEEDS = (1, 2, 3, 4, 5)

# 36 ticks * steps_per_tick=50 = 1800 internal steps -- comfortably inside the
# ~2000-step homeostatic-plateau window, matching test_protocell.py's already
# -validated margin (1800 steps) short of the ~2450-2650-step breakdown range.
CLOSED_LOOP_TICKS = 36
# 6 ticks * steps_per_tick=50 = 300 internal steps -- well past the <150-step
# collapse the Task-1 physics spike observed for this negative control.
CONTROL_TICKS = 6


def _run(name: str, n_ticks: int, seed: int = 1) -> dict:
    """Run a composite JSON from meta_modelers_guide/composites/ for n_ticks,
    with the Protocell `seed` config overridden, and return the final obs."""
    core = build_core()
    state = copy.deepcopy(
        json.loads((COMPOSITES / f"{name}.composite.json").read_text())["state"]
    )
    state["protocell"]["config"]["seed"] = seed
    comp = Composite({"state": state}, core=core)
    for _ in range(n_ticks):
        comp.run(1)
    return comp.state["obs"]


def test_closed_loop_persists():
    """The autopoietic closed loop (production gated on closure, self-limited
    by area) self-maintains within the ~2000-step window: persists == 1.0,
    a genuinely enclosed interior (not filled solid), and it never collapses
    within the window."""
    obs = _run("protocell-autopoietic", CLOSED_LOOP_TICKS)
    assert obs["persists"] == 1.0
    assert obs["enclosed_area"] > 0
    assert obs["collapse_tick"] == -1.0
    # the mass-held gate itself (persists ANDs enclosed_area>0 with
    # membrane_mass>mass_floor) -- assert the mass side explicitly too, so a
    # regression that satisfies area>0 via a degenerate near-zero-mass ring
    # would still be caught here even if `persists` were ever miscomputed.
    assert obs["membrane_mass"] > 0


def test_vesicle_control_collapses():
    """The vesicle control (k_prod=0, no internal production loop) has no
    feedback holding the boundary together: the ring dissipates via plain
    decay+diffusion and the interior stops being topologically enclosed."""
    obs = _run("protocell-vesicle-control", CONTROL_TICKS)
    assert obs["persists"] == 0.0
    assert obs["enclosed_area"] == 0.0
    assert obs["collapse_tick"] > 0


def test_persistence_is_multiseed_robust():
    """Vary the Protocell `seed` config across >=5 seeds (the documented
    interface for a future stochastic variant -- see module docstring on
    `seed` currently being inert for this deterministic RD physics). The
    qualitative contrast -- closed loop persists, control collapses -- must
    hold for EVERY seed; report the observed closed-loop enclosed-area range.
    """
    closed_areas = []
    control_areas = []
    for s in SEEDS:
        closed = _run("protocell-autopoietic", CLOSED_LOOP_TICKS, seed=s)
        control = _run("protocell-vesicle-control", CONTROL_TICKS, seed=s)

        assert closed["persists"] == 1.0, f"closed loop failed to persist at seed {s}"
        assert closed["enclosed_area"] > 0, f"closed loop lost enclosure at seed {s}"
        closed_areas.append(closed["enclosed_area"])

        assert control["persists"] == 0.0, f"control failed to collapse at seed {s}"
        assert control["enclosed_area"] == 0.0, f"control retained enclosure at seed {s}"
        control_areas.append(control["enclosed_area"])

    lo, hi = min(closed_areas), max(closed_areas)
    print(
        f"\nprotocell-autopoietic multi-seed (seeds {SEEDS[0]}-{SEEDS[-1]}, "
        f"{CLOSED_LOOP_TICKS} ticks): enclosed_area={closed_areas} "
        f"range=[{lo:.1f}, {hi:.1f}]; "
        f"protocell-vesicle-control: enclosed_area={control_areas} "
        f"(collapses to 0.0 every seed)"
    )

    # Loose range, not the exact observed point (149.0 at every seed on this
    # machine) -- see module docstring: `seed` is currently inert for this
    # deterministic physics, so today's range is degenerate, but this bound
    # is written to also hold if/when the process gains real per-seed noise.
    assert 50 < lo, f"lower end of the closed-loop area band too low: {lo:.1f}"
    assert hi < 300, f"upper end of the closed-loop area band too high: {hi:.1f}"
