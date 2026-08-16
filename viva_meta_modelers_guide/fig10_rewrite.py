"""Fig 10.1 as a GENUINE place-graph rewrite: chromosome segregation then cell
division, driven through the process-bigraph engine so a viewer can step the
changing topology frame by frame.

Unlike the pre-declared fig10-1-division composite (daughters already present),
this uses Milner reaction rules (bigraph_schema.assembly) over a `tree[node]`
store, so running it genuinely ADDS place-graph nodes at runtime:

  colony › cell › chromosome
     ── segregate ──▶  colony › cell › {chromosome_0, chromosome_1}
     ── divide   ──▶  colony › {cell_0, cell_1} each › {chromosome_0, chromosome_1}

A cell-cycle Process advances a clock and fires the right rewrite at the right
time, returning an `overwrite[tree[node]]` so removed keys actually disappear.
Custom rules preserve biological `_control` labels on the daughters (so a viewer
still renders them as cells/chromosomes) while a `_control: 'replicate'` MARK is
what triggers a rule — daughters drop the mark, so each event fires once and the
system reaches quiescence.
"""
from __future__ import annotations

import copy

from bigraph_schema.assembly import ReactionRule, Site, run_reactions
from process_bigraph import Process

MARK = "replicate"


def _f(d):
    return {"_type": "float", "_default": d}


def replicate_keeping_control(name: str, control: str, count: int = 2) -> ReactionRule:
    """A node marked `_control: MARK` with children under `contents` becomes `count`
    siblings `name_i`, each re-labelled `_control: control` (so it renders correctly
    and no longer matches the MARK redex → quiescence)."""
    return ReactionRule(
        redex={name: {"_control": MARK, "contents": Site()}},
        reactum={f"{name}_{i}": {"_control": control, "contents": Site()} for i in range(count)},
        instantiation={f"{name}_{i}": "contents" for i in range(count)},
        label=f"{control}:{name}->x{count}")


def _find_mark(node, target_control):
    """Walk a node tree; set the FIRST node whose _control == target_control to
    MARK (in place). Returns True if one was marked."""
    if not isinstance(node, dict):
        return False
    for k, v in node.items():
        if k.startswith("_") or not isinstance(v, dict):
            continue
        if v.get("_control") == target_control:
            v["_control"] = MARK
            return True
        if _find_mark(v, target_control):
            return True
    return False


class CellCycleDivision(Process):
    """Interval-driven cell cycle: at t≈`cycle` segregate the chromosome (1→2),
    at t≈2·`cycle` divide the cell (1→2 daughters). Each event is a genuine
    place-graph rewrite fired via run_reactions on the colony subtree."""
    config_schema = {"cycle": _f(3.0)}

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core)
        self._t = 0.0
        self._fired: set[str] = set()

    def inputs(self):
        return {"colony": "tree[node]"}

    def outputs(self):
        return {"colony": "overwrite[tree[node]]"}

    def update(self, state, interval):
        self._t += interval
        cyc = self.config["cycle"]
        colony = copy.deepcopy(state["colony"])

        if self._t >= cyc and "seg" not in self._fired:
            if _find_mark(colony, "chromosome"):
                colony, ev = run_reactions(
                    colony, [replicate_keeping_control("chromosome", "chromosome")],
                    max_steps=1, mode="deterministic")
                if ev:
                    self._fired.add("seg")
                    return {"colony": colony}
        elif self._t >= 2 * cyc and "div" not in self._fired:
            if _find_mark(colony, "cell"):
                colony, ev = run_reactions(
                    colony, [replicate_keeping_control("cell", "cell")],
                    max_steps=1, mode="deterministic")
                if ev:
                    self._fired.add("div")
                    return {"colony": colony}
        return {}


def _cell(dna=1.0):
    return {"_control": "cell",
            "contents": {"chromosome": {"_control": "chromosome",
                                        "contents": {"dna": dna}}}}


def build_fig10_division(cycle: float = 3.0, interval: float = 1.0):
    """Composite: a colony `tree[node]` holding one cell, a cell-cycle process
    that rewrites it, and a RAMEmitter capturing the WHOLE colony subtree each
    tick (so new nested nodes appear in the trajectory automatically)."""
    return {"state": {
        # tree[node] store: children inline alongside _type (NOT wrapped in _value)
        # — the shape the reaction engine matches on; an untyped store would drop
        # the _control tags the matcher needs.
        "colony": {"_type": "tree[node]", "cell": _cell()},
        "cell_cycle": {"_type": "process",
                       "address": "local:CellCycleDivision",
                       "interval": interval,
                       "config": {"cycle": cycle},
                       "inputs": {"colony": ["colony"]},
                       "outputs": {"colony": ["colony"]}},
        "emitter": {"_type": "step", "address": "local:RAMEmitter",
                    "config": {"emit": {"colony": "tree[node]", "time": "float"}},
                    "inputs": {"colony": ["colony"], "time": ["global_time"]}},
    }}
