"""Phase 4 · the composed whole cell runs the paper's full arc in one trajectory."""
from __future__ import annotations

from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core
from meta_modelers_guide.wholecell import build_whole_cell


def _run():
    core = build_core()
    sim = Composite(build_whole_cell(), core=core)
    sim.run(20.0)
    return gather_emitter_results(sim)[("emitter",)]


def test_whole_cell_builds_and_runs():
    rows = _run()
    assert len(rows) > 100


def test_cell_grows_then_divides():
    rows = _run()
    # biomass rises past the division threshold and the cell divides once (→ 2).
    assert max(r["biomass"] for r in rows) > 1.0
    assert max(r["cell_count"] for r in rows) == 2.0
    div_time = next(r["time"] for r in rows if r["cell_count"] >= 2)
    assert 0 < div_time < 12  # before the thermal shock


def test_thermal_shock_collapses_viability_and_disintegrates():
    rows = _run()
    # after the shock (t=12) temperature leaves the band, viability collapses,
    # and biomass decays into molecular debris.
    late = [r for r in rows if r["time"] >= 14]
    assert min(r["viability"] for r in late) < 0.1
    assert max(r["debris"] for r in rows) > 1.0
    # biomass ends well below its peak (the cell disintegrated).
    assert rows[-1]["biomass"] < 0.4 * max(r["biomass"] for r in rows)


def test_temperature_is_not_double_counted():
    rows = _run()
    # regression: the thermal driver uses set-semantics; the pre-shock temperature
    # must sit at the baseline (37), not 74.
    pre = [r["temperature"] for r in rows if r["time"] < 11]
    assert all(abs(t - 37.0) < 1e-6 for t in pre)
