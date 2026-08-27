"""Fig 8 · the minimal cell is an autopoietic closure.

The runnable fig08 composite (meta_modelers_guide.composites.fig08-runnable) wires the
six minimal-cell processes — containment, metabolism, gene-expression, replication,
diffusion and mass-action reactions — over FLAT scalar building-block pools (membrane,
lipids, metabolites, nutrients, amino_acids, nucleic_acids, enzymes, proteins, genes,
energy). The processes share those pools, so they mutually produce the components that
sustain each other. This test asserts the CLAIM the figure makes:

  (a) closure SUSTAINS itself — over the run every pool stays POSITIVE and BOUNDED
      (nothing collapses to zero, nothing blows up);
  (b) the template / catalytic pools (genes, energy, metabolites, nucleic acids) hold a
      steady balance while structural material (membrane, proteins) is net-produced;
  (c) mutual production is real — knock metabolism OUT and a downstream pool starves
      (metabolites collapse toward zero; energy, whose only source is metabolism, freezes
      at its seed instead of growing).

Complements test_compilation.py (that the fig08b handlers conform + compile). Mirrors
tests/test_fig10_topology.py: run the composite, assert over the emitted trajectory.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core

COMPOSITE = (
    Path(__file__).resolve().parent.parent
    / "meta_modelers_guide" / "composites" / "fig08-runnable.composite.json"
)

POOLS = ("membrane", "metabolites", "enzymes", "proteins",
         "genes", "energy", "nucleic_acids")


def _spec():
    return json.loads(COMPOSITE.read_text())


def _run(state, n_steps):
    core = build_core()
    sim = Composite({"state": state}, core=core)
    sim.run(n_steps)
    return gather_emitter_results(sim)[("emitter",)]


def _trajectory(state=None):
    spec = _spec()
    return _run(state if state is not None else spec["state"], spec["default_n_steps"])


def _series(rows, key):
    return [float(r[key]) for r in rows]


# ── (a) the closure sustains itself: positive + bounded ──────────────────────
def test_every_pool_stays_positive():
    rows = _trajectory()
    for k in POOLS:
        s = _series(rows, k)
        assert min(s) > 0.0, f"{k} collapsed to (or below) zero — closure broke"


def test_every_pool_stays_bounded():
    rows = _trajectory()
    for k in POOLS:
        s = _series(rows, k)
        # a real autopoietic balance neither explodes nor runs away over the run.
        assert max(s) < 1e3, f"{k} blew up ({max(s):.3g}) — closure not bounded"


def test_runs_default_n_steps():
    spec = _spec()
    rows = _trajectory()
    assert len(rows) == spec["default_n_steps"] + 1   # includes the t=0 emit


# ── (b) template pools hold steady while structural material is produced ──────
def test_template_pools_hold_a_steady_balance():
    rows = _trajectory()
    for k in ("genes", "energy", "metabolites", "nucleic_acids"):
        s = _series(rows, k)
        mid = s[len(s) // 2]
        rel = abs(s[-1] - mid) / max(mid, 1e-9)
        assert rel < 0.25, f"{k} did not hold a steady balance (rel drift {rel:.2f})"


def test_structural_material_is_net_produced():
    rows = _trajectory()
    for k in ("membrane", "proteins", "enzymes"):
        s = _series(rows, k)
        assert s[-1] > s[0], f"{k} was not net-produced by the closure"


# ── (c) mutual production: knock metabolism out and a downstream pool starves ─
def test_knocking_out_metabolism_starves_downstream_pools():
    """Metabolism is the sole source of the metabolite and energy pools. Remove it
    and those pools must respond: metabolites collapse toward zero (only the diffusion
    turnover remains), and energy — with no other source — freezes at its seed."""
    baseline = _trajectory()

    spec = _spec()
    knocked = copy.deepcopy(spec["state"])
    del knocked["metabolism"]                          # drive the process OFF
    ko = _run(knocked, spec["default_n_steps"])

    # metabolites: sustained under metabolism, starved without it.
    m_base = _series(baseline, "metabolites")[-1]
    m_ko = _series(ko, "metabolites")[-1]
    assert m_base > 0.2                                # the closure sustains it
    assert m_ko < 0.5 * m_base                         # removing metabolism starves it

    # energy: grows under metabolism, frozen at its seed without it.
    e_base = _series(baseline, "energy")
    e_ko = _series(ko, "energy")
    assert e_base[-1] > e_base[0]                       # metabolism grows the energy pool
    assert abs(e_ko[-1] - e_ko[0]) < 1e-9              # no source left → frozen
    assert e_ko[-1] < e_base[-1]                        # dependent pool responded


def test_gene_expression_sustains_the_enzymes_metabolism_depends_on():
    """Closure closes a LOOP, not just a chain (paper §Composition of the cellular
    interface — "each process's outputs sustain the inputs the others depend on").
    Gene expression is the sole source of the enzyme pool, and metabolism depends on
    those enzymes to turn nutrients into metabolites. Knock out gene expression and the
    loop opens: enzymes freeze exactly at their seed (no producer left) and metabolism's
    metabolite output falls — the coupling that sustains one process's inputs from
    another's outputs is what keeps the whole balance up."""
    baseline = _trajectory()

    spec = _spec()
    knocked = copy.deepcopy(spec["state"])
    del knocked["gene_expression"]                      # open the maintenance loop
    ko = _run(knocked, spec["default_n_steps"])

    # enzymes: grown by gene expression under closure, frozen at seed without it.
    enz_base = _series(baseline, "enzymes")
    enz_ko = _series(ko, "enzymes")
    assert enz_base[-1] > enz_base[0]                   # closure grows the enzyme pool
    assert abs(enz_ko[-1] - enz_ko[0]) < 1e-9          # sole source removed → frozen at seed

    # metabolism depends on those enzymes: its metabolite output falls once they stop growing.
    assert _series(ko, "metabolites")[-1] < _series(baseline, "metabolites")[-1]
