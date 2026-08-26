"""Fig 10 · biofilm emergence as a place-graph rewrite, asserted from the trajectory.

The runnable fig10-emergence composite runs a BiofilmEmergence process over an
environment `tree[node]`: free motile bacteria (top-level siblings) ATTACH and
aggregate into a nested biofilm microcolony (sessile), then the community MATURES
by secreting ECM matrix nodes. This test asserts the figure's principle FROM THE
EMITTED TRAJECTORY:

  (a) free (planktonic) cells fall to 0 while biofilm-nested cells rise — the
      dispersed population collapses into one nested community (attach + aggregate);
  (b) ECM appears only AFTER maturation, i.e. strictly after attachment.

Mirrors the trajectory-driven style of tests/test_fig10_topology.py.
"""
from __future__ import annotations

import json
from pathlib import Path

from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core

COMPOSITE = (
    Path(__file__).resolve().parent.parent
    / "meta_modelers_guide" / "composites" / "fig10-emergence.composite.json"
)


def _top_nodes(tree: dict, ctrl: str):
    return [k for k, v in tree.items()
            if not k.startswith("_") and isinstance(v, dict) and v.get("_control") == ctrl]


def _env_counts(env: dict):
    """(#free top-level cells, #biofilm-nested cells, #ecm nodes) for one env frame."""
    free = len(_top_nodes(env, "cell"))
    nested = ecm = 0
    bf = env.get("biofilm")
    if isinstance(bf, dict):
        contents = bf.get("contents", {})
        nested = sum(1 for v in contents.values()
                     if isinstance(v, dict) and v.get("_control") == "cell")
        ecm = sum(1 for v in contents.values()
                  if isinstance(v, dict) and v.get("_control") == "ecm")
    return free, nested, ecm


def _trajectory():
    spec = json.loads(COMPOSITE.read_text())
    core = build_core()
    sim = Composite({"state": spec["state"]}, core=core)
    sim.run(spec["default_n_steps"])
    rows = gather_emitter_results(sim)[("emitter",)]
    return [_env_counts(r["env"]) for r in rows]


def test_free_cells_attach_into_a_nested_biofilm():
    traj = _trajectory()
    free = [c[0] for c in traj]
    nested = [c[1] for c in traj]
    assert free[0] > 0 and nested[0] == 0            # start: dispersed, none nested
    assert free[-1] == 0                              # all planktonic cells attach
    assert max(nested) == free[0]                     # every free cell ends up nested
    # attachment CONSERVES the cells: at the attach step, free → 0 and nested → all.
    attach_i = next(i for i in range(len(nested)) if nested[i] > 0)
    assert free[attach_i] == 0
    assert nested[attach_i] == free[0]


def test_ecm_appears_only_after_maturation():
    traj = _trajectory()
    nested = [c[1] for c in traj]
    ecm = [c[2] for c in traj]
    assert ecm[0] == 0
    assert max(ecm) > 0                                # matured community secretes ECM
    attach_i = next(i for i in range(len(nested)) if nested[i] > 0)
    mature_i = next(i for i in range(len(ecm)) if ecm[i] > 0)
    assert mature_i > attach_i                         # ECM only after attachment
    # ECM only ever exists while the sessile community is present (nested cells > 0).
    for f, n, e in traj:
        if e > 0:
            assert n > 0
