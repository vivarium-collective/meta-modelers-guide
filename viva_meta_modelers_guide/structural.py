"""Fig 10-1 division as a GENUINE structural rewrite (process-bigraph's BRS).

The ``DivisionRewrite`` handler in ``handlers_fig10.py`` animates a *pre-declared*
post-structure: the daughter stores already exist in the place graph and the
handler fills them. This module realizes the same biology as a **true structural
rewrite** using process-bigraph's built-in bigraphical reactive system (re-exported
by ``viva-compiler``): a parametric ``ReactionRule`` whose reactum has a different
node set than its redex, so firing it **creates** the daughter nodes — one ``cell``
node genuinely *becomes* two, carrying its contents (biomass, DNA) into each
(Milner §8.1 shared site).

    {"cell": {contents}}  --divide-->  {"daughter_1": {contents}, "daughter_2": {contents}}

This is the honest realization of the paper's Fig 3c event-driven rewrite.

This works two ways, both genuine node creation:

* :func:`run_division` — fired *inside a live* ``Composite`` via a ``ReactionStep``
  over a ``tree[node]``-typed store (the recommended path).
* :func:`divide` — driven by ``run_reactions`` on the node subtree directly (the
  same engine, no composite).

The store MUST be typed ``tree[node]``: a composite realizes an untyped store as a
plain dict, dropping the ``_control`` tags the matcher needs — the reaction then
silently no-ops (process-bigraph now *warns* about this, see PR #193). With the
store typed, the ``ReactionStep`` fires on ``run()`` and the daughters are created.
"""
from __future__ import annotations

from process_bigraph import Composite, allocate_core

from viva_compiler import ReactionRule, reaction_step_node, run_reactions

try:                                    # Site() marks a parametric hole in the pattern
    from bigraph_schema.assembly import Site
except Exception:                       # pragma: no cover
    from bigraph_schema import Site


def cell_division_rule(rate: float | None = None) -> ReactionRule:
    """A parametric division rule: any ``cell`` node (with arbitrary ``contents``)
    is replaced by two ``cell`` daughters, each receiving the matched contents."""
    return ReactionRule(
        redex={"cell": {"_control": "cell", "contents": Site()}},
        reactum={"daughter_1": {"_control": "cell", "contents": Site()},
                 "daughter_2": {"_control": "cell", "contents": Site()}},
        instantiation={"contents": "contents"},   # both daughters share the contents
        rate=rate,
        label="divide",
    )


def one_cell(biomass: float = 1.0, dna: float = 1.0) -> dict:
    """A colony holding a single cell node with the division-relevant contents."""
    return {"cell": {"_control": "cell", "contents": {"biomass": biomass, "dna": dna}}}


def divide(colony: dict, mode: str = "deterministic", seed: int | None = None) -> dict:
    """Fire one division on ``colony`` (a node subtree) and return the rewritten
    colony — a genuine structural rewrite that creates the daughter nodes."""
    kwargs = {"max_steps": 1, "mode": mode}
    if seed is not None:
        import random
        kwargs["rng"] = random.Random(seed)
    final, _events = run_reactions(colony, [cell_division_rule()], **kwargs)
    return final


def cells_in(colony: dict) -> list[str]:
    """The keys of the cell nodes in a colony (control == 'cell')."""
    return [k for k, v in colony.items()
            if isinstance(v, dict) and v.get("_control") == "cell"]


# ── genuine division INSIDE a live Composite (a ReactionStep) ─────────────────
def dividing_composite(biomass: float = 1.0, dna: float = 1.0) -> dict:
    """A composite whose ``colony`` store (typed ``tree[node]``) holds one cell and
    a ``ReactionStep`` that divides it. Typing the store is essential — an untyped
    store is realized as a plain dict and the reaction silently no-ops."""
    return {"state": {
        "colony": {"_type": "tree[node]",
                   "cell": {"_control": "cell", "contents": {"biomass": biomass, "dna": dna}}},
        "divider": reaction_step_node([cell_division_rule()], ["colony"]),
    }}


def run_division(biomass: float = 1.0, dna: float = 1.0, core=None) -> dict:
    """Build the dividing composite, run one step, and return the resulting colony.
    The ``ReactionStep`` fires the division inside the live composite: the single
    cell node is genuinely replaced by two daughter cell nodes."""
    if core is None:
        core = allocate_core()
    sim = Composite(dividing_composite(biomass, dna), core=core)
    sim.run(1)
    return sim.state["colony"]
