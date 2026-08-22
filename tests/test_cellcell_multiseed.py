"""Multi-seed robustness for the cell-cell competition headline number.

THE CONVENTION (studies 5/7/9 copy this): a CPM headline number is a single-seed
point on a stochastic Metropolis trajectory. The honest claim is a RANGE across
seeds, not the one seed that happened to be hard-coded. This module establishes
the pattern once, cheaply, on the single most seed-sensitive headline in the
investigation -- `cell-cell-coupling-spatial`'s competition ratio (the reviewer
flagged the single-seed 3.69x as dominated by finite-size / trajectory artifacts,
Part E-10 / D-5 of docs/superpowers/reviews/2026-08-21-fable-investigation-review.md).

How to copy this to another study:
  1. make the process read its CPM seed from config (`int(c.get("seed", 1))`),
     defaulting to 1 so every composite stays deterministic (colony_field.py did this);
  2. deep-copy the composite state, set `state[<proc>]["config"]["seed"] = s`, run;
  3. assert the QUALITATIVE claim holds for EVERY seed, and report the numeric RANGE.

Observed over seeds 1-5 (20-tick `cellcell-compete` run, this machine):
    seed 1: ratio 3.69   <- the hard-coded single-seed headline (the TOP of the band)
    seed 2: ratio 3.12
    seed 3: ratio 2.90
    seed 4: ratio 3.31
    seed 5: ratio 2.89
    range [2.9x, 3.7x], mean ~3.2x; the faster competitor (id 1, glucose_vmax 10)
    wins EVERY seed. The single-seed 3.69x is the flattering end, not the middle.
"""
from __future__ import annotations
import copy
import json
from pathlib import Path

import pytest

pytest.importorskip("cobra")
pytest.importorskip("cpm")
pytest.importorskip("spatio_flux")

from process_bigraph import Composite  # noqa: E402
from meta_modelers_guide.core import build_core  # noqa: E402

COMPOSITES = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"
SEEDS = (1, 2, 3, 4, 5)
STEPS = 20


def _compete_ratio(seed: int) -> tuple[float, dict]:
    """Run the competition composite at a given CPM seed; return the winner/loser
    biomass ratio and the raw obs. The seed is injected into the CpmColonyField
    config only -- nothing else about the composite changes."""
    core = build_core()
    state = copy.deepcopy(
        json.loads((COMPOSITES / "cellcell-compete.composite.json").read_text())["state"]
    )
    state["colony"]["config"]["seed"] = seed
    comp = Composite({"state": state}, core=core)
    comp.run(STEPS)
    obs = comp.state["obs"]
    ratio = obs["biomass"]["1"] / obs["biomass"]["2"]
    return ratio, obs


def test_competition_margin_holds_as_a_range_across_seeds():
    """The competition headline (id-1 / id-2 biomass ratio) is a seed-sensitive
    number. Assert the QUALITATIVE claim -- the faster competitor (id 1) excludes
    the slower one -- for every seed, and pin the numeric RANGE with margin, so the
    single-seed 3.69x headline is reported as the top of a band, not as the result."""
    ratios = []
    for s in SEEDS:
        ratio, obs = _compete_ratio(s)
        ratios.append(ratio)
        # the faster competitor (id 1, glucose_vmax 10) wins on both biomass AND
        # lattice volume, EVERY seed -- the exclusion direction is seed-robust.
        assert obs["biomass"]["1"] > obs["biomass"]["2"], f"winner flipped at seed {s}"
        assert obs["volume"]["1"] > obs["volume"]["2"], f"volume winner flipped at seed {s}"
        # the study's own pass threshold (> 1.5x) holds for every seed, not just seed 1.
        assert ratio > 1.5, f"margin collapsed below 1.5x at seed {s}: {ratio:.2f}"

    lo, hi, mean = min(ratios), max(ratios), sum(ratios) / len(ratios)
    print(
        f"\ncellcell-compete multi-seed (seeds {SEEDS[0]}-{SEEDS[-1]}): "
        f"ratios={[round(r, 2) for r in ratios]} "
        f"range=[{lo:.2f}x, {hi:.2f}x] mean={mean:.2f}x"
    )

    # RANGE assertions, set with margin (not at the observed edge) so the test is a
    # robustness gate, not a brittle golden-value check. The observed band is
    # [2.89, 3.69]; the loose band below tolerates cross-platform CPM-RNG drift.
    assert 2.0 < lo, f"lower end of the band too low: {lo:.2f}"
    assert hi < 4.5, f"upper end of the band too high: {hi:.2f}"
    assert 2.5 < mean < 4.0, f"mean margin outside expected band: {mean:.2f}"
    # the headline single-seed number (3.69x) must NOT be representative of the
    # whole band -- at least one seed comes in materially lower, which is the entire
    # point of reporting a range rather than the one hard-coded seed.
    assert lo < 3.4, (
        "every seed matched the 3.69x headline -- the range is suspiciously tight; "
        "the multi-seed convention exists precisely because it usually is not."
    )
