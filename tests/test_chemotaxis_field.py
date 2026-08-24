# tests/test_chemotaxis_field.py
"""CHEMOTAXIS variant of the flagship: the cell now ACTS on what it senses, moving
directed UP the shared glucose gradient. Closes the sense -> metabolize -> act loop the
flagship deferred.

Mechanism (CpmCellField.chemotaxis_strength): each tick the coupling process reads the
shared spatio-flux glucose field, takes grad(glucose) over the cell's footprint, and sets
viva-cpm's per-type external-potential force f = strength * grad(glucose). The Metropolis
pixel-copy then favours copies that move the footprint up-gradient (U(r) = -f.r), the
linearized form of CC3D chemotaxis. strength 0.0 -> OFF (no force set, flagship
byte-identical); 50.0 -> the chemotaxis variant.

Skipped when the optional cobra/cpm/spatio_flux deps are absent (as the flagship module)."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import numpy as np
import pytest
from process_bigraph import Composite
from meta_modelers_guide.core import build_core

pytest.importorskip("cobra")
pytest.importorskip("cpm")
pytest.importorskip("spatio_flux")

_COMPOSITES = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"
COMP = _COMPOSITES / "single-cell-in-a-field.composite.json"
COMP_CHEMO = _COMPOSITES / "single-cell-in-a-field-chemotaxis.composite.json"

# Seed block [15,27,0,22,34,1] -> initial COM ~ (18.5, 30.5). The field's glucose
# gradient runs left-low (x=0, 0.3) to right-high (x=59, 3.0), so "up-gradient" is +x.
SEED_X = 18.5


def _run(comp_path, ticks=20):
    core = build_core()
    state = json.loads(comp_path.read_text())["state"]
    comp = Composite({"state": state}, core=core)
    glc0 = float(np.asarray(comp.state["fields"]["glucose"]).sum())
    comp.run(ticks)
    obs = comp.state["obs"]
    return {
        "x": float(obs["position"][0]),
        "y": float(obs["position"][1]),
        "biomass": float(obs["biomass"]),
        "volume": float(obs["volume"]),
        "net_glucose": glc0 - float(np.asarray(comp.state["fields"]["glucose"]).sum()),
        "local_nutrient": float(obs["local_nutrient"]),
    }


def test_chemotaxis_moves_cell_up_gradient_and_helps_growth():
    """The chemotaxis cell moves directed UP the sensed glucose gradient (+x) while the
    non-motile flagship control barely drifts, and it acquires more glucose and grows more
    for reaching the richer region — a genuine, measured directed-motion advantage."""
    control = _run(COMP)          # chemotaxis_strength 0.0 (flagship)
    chemo = _run(COMP_CHEMO)      # chemotaxis_strength 50.0

    ctrl_dx = control["x"] - SEED_X
    chemo_dx = chemo["x"] - SEED_X

    # 1) DIRECTED MOTION: the chemotaxis cell migrates far up-gradient (+x); the control
    #    barely moves (thermal drift only). Measured: control dx ~+0.2, chemo dx ~+20.8.
    assert ctrl_dx < 2.0, f"control should barely drift up-gradient, got dx={ctrl_dx:+.2f}"
    assert chemo_dx > 10.0, f"chemotaxis should migrate up-gradient, got dx={chemo_dx:+.2f}"
    assert chemo_dx > 5.0 * max(ctrl_dx, 0.1), "chemotaxis dx should dwarf control dx"

    # 2) IT REACHES A RICHER REGION: sensed local glucose is markedly higher for the
    #    migrating cell (measured ~1.95 vs the control's ~0.94).
    assert chemo["local_nutrient"] > 1.5 * control["local_nutrient"]

    # 3) IT HELPS: more glucose acquired and more growth than the stationary control on
    #    the SAME field (measured: net glucose 36.8 vs 31.6; biomass 0.418 vs 0.370;
    #    volume 150 vs 110).
    assert chemo["net_glucose"] > control["net_glucose"]
    assert chemo["biomass"] > control["biomass"]
    assert chemo["volume"] > control["volume"]


def test_chemotaxis_off_is_byte_identical_to_flagship():
    """Regression pin: chemotaxis_strength 0.0 leaves the flagship trajectory unchanged.
    The new term is a pure no-op when off (set_external_potential is never called, so the
    world's ext-potential stays zero) — so a run with the flag EXPLICITLY 0.0 is identical,
    to the bit, to a run with the flag ABSENT (the flagship default). That equality is the
    byte-identical guarantee."""
    def run_flag(value):
        core = build_core()
        state = copy.deepcopy(json.loads(COMP.read_text())["state"])
        if value is not None:
            state["cell"]["config"]["chemotaxis_strength"] = value
        comp = Composite({"state": state}, core=core)
        comp.run(20)
        o = comp.state["obs"]
        return (float(o["biomass"]), float(o["volume"]),
                float(o["position"][0]), float(o["position"][1]))

    absent = run_flag(None)     # flag not present -> config default 0.0
    explicit = run_flag(0.0)    # flag present, explicitly 0.0
    assert absent == explicit, f"chemotaxis off must be a no-op: {absent} != {explicit}"

    # And the flagship endpoints are unchanged (its own pins: biomass ~0.37, volume 110,
    # only thermal up-gradient drift).
    biomass, volume, x, _ = explicit
    assert abs(biomass - 0.3695) < 1e-4
    assert volume == 110.0
    assert (x - SEED_X) < 2.0
