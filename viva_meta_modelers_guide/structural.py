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

Known integration gap (documented, not worked around): firing this as a live
``ReactionStep`` *inside a running* ``Composite`` currently doesn't work, because
the composite's ``tree[node]`` realize strips the ``_control`` tags the matcher
needs (the reaction machinery operates on the raw node dict, which ``run_reactions``
uses directly). Wiring the reaction engine through composite realize is a
process-bigraph framework task; here we drive it via ``run_reactions`` on the node
subtree, which is the same engine.
"""
from __future__ import annotations

from viva_compiler import ReactionRule, run_reactions

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
