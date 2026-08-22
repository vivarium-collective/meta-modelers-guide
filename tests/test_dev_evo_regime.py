# tests/test_dev_evo_regime.py
"""Study-9 Task 4: lock the two demonstrating claims of `CpmEvolution`
(`meta_modelers_guide/cpm/evolution.py`) in a regression test, reported as a
multi-seed FRACTION (the convention `tests/test_cellcell_multiseed.py`
established) rather than a single-seed headline:

- DEVELOPMENT: `development-evolution-spatial` grows a colony whose radial
  core-vs-rim glucose heterogeneity (`rim_core_ratio`) emerges above 1.0 --
  the core is more depleted than the rim by the end of the run.
- EVOLUTION: across seeds, the selection-ON composite's population mean
  `vmax` shifts up in most seeds; the no-mutation control never shifts (no
  raw material); the no-selection control mutates (`var_vmax > 0`) but does
  NOT consistently shift up (undirected drift) -- isolating SELECTION, not
  mutation alone, as the cause of the directional trait shift.

Evolution is stochastic (one selection seed can reverse -- see the API map,
`docs/superpowers/api-maps/2026-08-22-development-and-evolution-api-map.md`
Q("EVOLUTION"), seeds 1-5: selection UP in 4/5, no-mutation 0/5, no-selection
2/5). Assert FRACTIONS with margin, not every seed.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

pytest.importorskip("cpm")
pytest.importorskip("spatio_flux")
pytest.importorskip("cobra")

from process_bigraph import Composite  # noqa: E402

from meta_modelers_guide.core import build_core  # noqa: E402

COMPOSITES = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"

SEEDS = (1, 2, 3, 4, 5)
STEPS = 45
VMAX0 = 1.5
# margin above the founder value before a seed counts as "shifted up" -- small
# enough not to hide a real (if modest) selection signal, large enough that
# float noise / a near-zero drift doesn't spuriously count as a "shift".
UP_MARGIN = 0.05


def _run(composite_name: str, seed: int, steps: int = STEPS) -> dict:
    """Load a study-9 composite, override the CpmEvolution `seed` (threads
    into both `load_world`'s potts spec and the mutation RNG -- verified in
    Task 1/2), run it, and return the final `obs` dict."""
    core = build_core()
    state = copy.deepcopy(
        json.loads((COMPOSITES / f"{composite_name}.composite.json").read_text())["state"]
    )
    state["evo"]["config"]["seed"] = seed
    comp = Composite({"state": state}, core=core)
    comp.run(steps)
    return comp.state["obs"]


def _sweep(composite_name: str, seeds=SEEDS, steps: int = STEPS) -> list[tuple[int, dict]]:
    return [(s, _run(composite_name, s, steps=steps)) for s in seeds]


# ---------------------------------------------------------------------------
# 1. Development: core-vs-rim heterogeneity emerges.
# ---------------------------------------------------------------------------

def test_development_heterogeneity_emerges():
    """`rim_core_ratio` starts near 1.0 (no readable gradient yet, few cells)
    and ends CLEARLY above 1.0 -- the colony's core is more glucose-depleted
    than its rim by the end of a 45-tick run (Fig 10c-d's "collective
    interface"), the development half of study 9's demonstration."""
    seed = SEEDS[2]  # seed 3 -- the composites' own default/flagship seed
    early = _run("development-evolution-spatial", seed, steps=5)
    late = _run("development-evolution-spatial", seed, steps=STEPS)

    early_ratio = early["rim_core_ratio"]
    late_ratio = late["rim_core_ratio"]
    print(f"\nrim_core_ratio (seed {seed}): early(5 ticks)={early_ratio:.4f} "
          f"late({STEPS} ticks)={late_ratio:.4f}")

    # early on there are few divisions yet, so the metric is close to its 1.0
    # floor (no readable core/rim split); give it generous headroom rather
    # than pin an exact value.
    assert early_ratio < 1.2, (
        f"rim_core_ratio already elevated at 5 ticks ({early_ratio}) -- "
        "expected it to start near the 1.0 floor")
    # by the end of the run the heterogeneity is unambiguous.
    assert late_ratio > 1.2, (
        f"rim_core_ratio {late_ratio} at {STEPS} ticks shows no clear "
        "emergent core/rim heterogeneity")
    assert late_ratio > early_ratio, (
        "rim_core_ratio did not grow from the start of the run to the end "
        f"({early_ratio} -> {late_ratio})")


# ---------------------------------------------------------------------------
# 2. Evolution: selection-ON shifts the mean trait up, multi-seed FRACTION.
# ---------------------------------------------------------------------------

def test_evolution_shifts_trait_under_selection():
    """Across >=5 seeds, the selection-ON colony's population mean `vmax`
    ends above `vmax0` (+ a small margin) in MOST seeds -- assert the
    FRACTION (>=4/5, or the robust fraction actually observed), not every
    seed; evolution is a stochastic Metropolis trajectory and one seed may
    reverse (API map: seeds 1-5 -> UP in 4/5, delta range [-0.116, +0.700])."""
    results = _sweep("development-evolution-spatial", SEEDS)
    deltas = [(seed, obs["mean_vmax"] - VMAX0) for seed, obs in results]
    up = [seed for seed, delta in deltas if delta > UP_MARGIN]

    lo = min(d for _, d in deltas)
    hi = max(d for _, d in deltas)
    print(f"\nselection-ON multi-seed (seeds {SEEDS}): "
          f"deltas={[(s, round(d, 3)) for s, d in deltas]} "
          f"up={len(up)}/{len(SEEDS)} range=[{lo:+.3f}, {hi:+.3f}]")

    for seed, obs in results:
        assert obs["var_vmax"] > 0.0, f"seed {seed}: no mutational variance built up"
        assert obs["n_cells"] >= 5, f"seed {seed}: too few cells for a meaningful signal"

    assert len(up) >= 4, (
        f"only {len(up)}/{len(SEEDS)} seeds shifted mean_vmax up under selection "
        f"(deltas={deltas}); expected >=4/5")


# ---------------------------------------------------------------------------
# 3. No-mutation control: static, EVERY seed.
# ---------------------------------------------------------------------------

def test_no_mutation_control_is_static():
    """With `mutate: false` (a BOOLEAN flag, not `mut_sigma=0.0` -- which
    bigraph_schema silently drops), the trait cannot vary across divisions:
    mean stays EXACTLY the founder value and variance is EXACTLY 0 in every
    seed (0/5 shift) -- no raw material for selection to act on."""
    results = _sweep("development-evolution-no-mutation", SEEDS)
    for seed, obs in results:
        assert obs["mean_vmax"] == pytest.approx(VMAX0, abs=1e-9), (
            f"seed {seed}: mean_vmax drifted from founder under mutate=false")
        assert obs["var_vmax"] == pytest.approx(0.0, abs=1e-9), (
            f"seed {seed}: var_vmax nonzero under mutate=false")
        assert obs["n_cells"] >= 2, f"seed {seed}: need at least one division to exercise the control"
    print(f"\nno-mutation control (seeds {SEEDS}): mean_vmax == {VMAX0} "
          "and var_vmax == 0.0 in every seed (0/5 shift), as expected")


# ---------------------------------------------------------------------------
# 4. No-selection control: mutates but does not directionally shift.
# ---------------------------------------------------------------------------

def test_no_selection_control_does_not_directionally_shift():
    """With `selection: false` the trait still mutates on division
    (`var_vmax > 0` -- raw variance builds up) but every cell's dFBA uses the
    FIXED founder `vmax0` regardless of its own trait, so the trait confers
    no fitness: any drift in the population mean is undirected. Assert the
    up-fraction is clearly LOWER than the selection-ON arm (isolating
    SELECTION, not mutation alone, as the cause of the directional shift;
    API map: seeds 1-5 -> UP in 2/5, delta range [-0.270, +0.112])."""
    results = _sweep("development-evolution-no-selection", SEEDS)
    deltas = [(seed, obs["mean_vmax"] - VMAX0) for seed, obs in results]
    up = [seed for seed, delta in deltas if delta > UP_MARGIN]
    mean_delta = sum(d for _, d in deltas) / len(deltas)

    lo = min(d for _, d in deltas)
    hi = max(d for _, d in deltas)
    print(f"\nno-selection control multi-seed (seeds {SEEDS}): "
          f"deltas={[(s, round(d, 3)) for s, d in deltas]} "
          f"up={len(up)}/{len(SEEDS)} range=[{lo:+.3f}, {hi:+.3f}] mean={mean_delta:+.3f}")

    for seed, obs in results:
        assert obs["var_vmax"] > 0.0, (
            f"seed {seed}: no mutational variance built up under selection=false "
            "(the trait should still mutate, just confer no fitness)")

    # the up-fraction under no-selection must be clearly lower than the
    # selection-ON arm's (>=4/5): allow at most half the seeds to drift up,
    # and/or the mean shift must be small/near-zero (no directional signal).
    assert len(up) <= 2, (
        f"{len(up)}/{len(SEEDS)} no-selection seeds shifted up -- too close to "
        "the selection-ON fraction to isolate selection as the cause")
    assert abs(mean_delta) < 0.3, (
        f"no-selection mean delta {mean_delta:+.3f} too large -- looks directional, "
        "not undirected drift")
