"""The disintegration composite, when played, SHOWS disintegration: the thermal
environment leaves the viable band, viability collapses below the floor, and
biomass turns into molecular debris (the cell→molecular level shift, Fig 6a)."""
from __future__ import annotations

from process_bigraph import Composite

from meta_modelers_guide.core import build_core
from meta_modelers_guide.wholecell import build_disintegration


def test_playing_the_composite_shows_disintegration():
    core = build_core()
    comp = Composite(build_disintegration(emit=False), core=core)
    v0 = comp.state["cell"]["viability"]
    comp.run(20)
    v_end = comp.state["cell"]["viability"]
    debris = comp.state["cell"]["debris"]
    biomass = comp.state["cell"]["biomass"]
    assert v0 > 0.9, "starts viable"
    assert v_end < 0.3, f"viability should collapse past the floor, got {v_end}"
    assert debris > 0.0, f"biomass should disintegrate into molecular debris, got {debris}"
    assert biomass >= 0.0
