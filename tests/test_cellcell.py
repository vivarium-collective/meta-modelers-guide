"""Cell–cell coupling: two cell interfaces coupled through one shared nutrient
store negotiate viability. Competition drives the weaker cell out of its viable
band while the stronger persists; a cross-feeding handler over the SAME coupling
interface stabilizes both (law 4). Interface preserved under compilation (law 2)."""
from __future__ import annotations

import json
from pathlib import Path

from process_bigraph import Composite

from meta_modelers_guide.core import build_core
from meta_modelers_guide.compile import compile_composite, interface_of
from meta_modelers_guide.handler_envs import ENVS

COMPOSITES = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"


def _sem():
    return json.loads((COMPOSITES / "cellcell-coupling.composite.json").read_text())["state"]


def _run(env_name):
    core = build_core()
    ex = compile_composite(_sem(), ENVS[env_name], core)
    assert interface_of(ex) == interface_of(_sem())  # law 2
    comp = Composite({"state": ex}, core=core)
    comp.run(20)
    return comp.state


def test_competition_pushes_weaker_cell_out_of_viable_bounds():
    st = _run("cellcell-compete")
    va = st["cell_a"]["viability"]
    vb = st["cell_b"]["viability"]
    # cell_a has the higher uptake capacity → it stays viable and cell_b starves.
    assert va > 0.5 and vb < 0.5, f"expected a>0.5>b, got a={va} b={vb}"
    # shared resource actually depleted (coupling is real, not two isolated cells)
    assert st["env"]["nutrient"] < 1.0


def test_crossfeeding_keeps_both_cells_viable():
    st = _run("cellcell-crossfeed")
    va = st["cell_a"]["viability"]
    vb = st["cell_b"]["viability"]
    assert va > 0.5 and vb > 0.5, f"cross-feeding should sustain both, got a={va} b={vb}"


def test_handler_independence_same_interface():
    # law 4: competition and cross-feeding are two handler envs over ONE interface.
    core = build_core()
    compete = compile_composite(_sem(), ENVS["cellcell-compete"], core)
    crossfeed = compile_composite(_sem(), ENVS["cellcell-crossfeed"], core)
    assert interface_of(compete) == interface_of(crossfeed) == interface_of(_sem())
