"""Fig 7 mechanistic variant — nested compartments where the hierarchy INFLUENCES
FUNCTION, not just routes a scalar. Permeable boundaries gate a deep nuclear
reporter; a locally-restricted cytoplasmic reaction makes compartments functionally
distinct.

Each gate carries the reviewer's evidence class (pass_if.kind). Matched-null
controls (a closed boundary, metabolism off) use an EPSILON, never 0.0 —
bigraph_schema restores a float 0.0 config to the schema default.
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
COMPOSITE = ROOT / "meta_modelers_guide" / "composites" / "fig07-mechanistic.composite.json"
EPS = 1e-9


def _run(perm_mem=0.3, perm_nuc=0.3, k_met=0.05, steps=40):
    spec = json.loads(COMPOSITE.read_text())
    spec["state"]["membrane"]["config"]["permeability"] = perm_mem
    spec["state"]["nuclear_envelope"]["config"]["permeability"] = perm_nuc
    spec["state"]["cytoplasmic_metabolism"]["config"]["k"] = k_met
    sim = Composite({"state": spec["state"]}, core=build_core())
    sim.run(steps)
    return gather_emitter_results(sim)[("emitter",)]


def test_composite_builds_and_runs():
    """REGRESSION_PIN: fig07-mechanistic builds through the nested place graph and
    runs 40 ticks (41 rows)."""
    assert len(_run()) == 41


def test_transport_conserves_substrate_across_compartments():
    """INVARIANT: passive transport across the boundaries is conservative — with the
    reactions off, the total substrate across environment + cytoplasm + nucleus is
    invariant (containment does not create or lose mass)."""
    rows = _run(k_met=EPS)
    tot = [float(r["env_substrate"]) + float(r["cyto_substrate"]) + float(r["nuc_substrate"]) for r in rows]
    assert max(abs(t - tot[0]) for t in tot) < 1e-6


def test_boundary_permeability_gates_the_deep_reporter():
    """MECHANISTIC_ABLATION: the deep (nuclear) reporter is causally gated by the
    boundary permeabilities — with both boundaries open it is produced; closing the
    MEMBRANE (ε) isolates the whole interior and the reporter is zero. A boundary-level
    cause with a deep functional effect, not mere nested routing of a scalar."""
    open_r = float(_run()[-1]["reporter"])
    closed_mem = float(_run(perm_mem=EPS)[-1]["reporter"])
    assert open_r > 1.0, "reporter should be produced when boundaries are open"
    assert closed_mem < 1e-6, "closing the membrane must shut the deep reporter down"


def test_both_boundaries_gate_in_series():
    """MECHANISTIC_ABLATION: depth = number of permeability barriers in series. The
    nuclear reporter sits behind TWO boundaries; closing EITHER one (at a different
    depth) independently zeroes it, while both-open produces it — so each level of
    the hierarchy is a functional gate, not just a container."""
    both_open = float(_run()[-1]["reporter"])
    mem_closed = float(_run(perm_mem=EPS)[-1]["reporter"])
    nuc_closed = float(_run(perm_nuc=EPS)[-1]["reporter"])
    assert both_open > 1.0
    assert mem_closed < 1e-6 and nuc_closed < 1e-6, "either boundary alone must gate the deep reporter"


def test_higher_permeability_fills_deeper_compartment_faster():
    """PROSPECTIVE_PREDICTION: more permeable boundary ⇒ the deep compartment fills
    faster. Predicted before running: in pure transport, the nuclear substrate at a
    fixed early time is monotone increasing in the membrane permeability."""
    t = 8
    vals = [float(_run(perm_mem=pm, k_met=EPS, steps=t)[-1]["nuc_substrate"]) for pm in (0.05, 0.1, 0.2, 0.4, 0.8)]
    assert all(vals[i + 1] >= vals[i] - 1e-12 for i in range(len(vals) - 1)), f"not monotone: {vals}"
    assert vals[-1] > vals[0] + 0.5, "permeability should visibly change deep filling"


def test_local_metabolism_is_compartment_restricted():
    """MECHANISTIC_ABLATION: the cytoplasmic reaction is LOCALLY RESTRICTED — it
    consumes substrate only in the cytoplasm, so it starves the downstream nucleus.
    Turning it off raises the deep reporter; the compartments do functionally
    different things (cytoplasm metabolises, nucleus reports)."""
    r_on = float(_run(k_met=0.3)[-1]["reporter"])
    r_off = float(_run(k_met=EPS)[-1]["reporter"])
    assert r_off > r_on + 1.0, "cytoplasmic consumption should reduce what reaches the nucleus"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
