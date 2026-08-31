"""Fig 9b (division) as a GENUINE, REPEATING place-graph rewrite: a cell cycle
that runs the whole colony through chromosome replication then cell division,
over and over, driven through the process-bigraph engine so a viewer can step the
changing topology frame by frame.

Unlike the pre-declared fig09-division composite (daughters already present),
running this genuinely ADDS place-graph nodes at runtime, and keeps dividing:

  colony › cell › chromosome
     ── replicate ──▶  colony › cell › {chromosome_0, chromosome_1}
     ── divide    ──▶  colony › {cell_0, cell_1} each › chromosome
     ── replicate ──▶  each daughter's chromosome duplicates …
     ── divide    ──▶  colony › {cell_1..4} …   → 1 → 2 → 4 → 8 …

The CellCycleDivision Process advances a clock and, every `cycle`, alternates the
two rewrites across EVERY cell, returning an `overwrite[tree[node]]` so removed
keys actually disappear. A `capacity` cap keeps the tree finite; the first cycle
is still replicate-then-divide, so the Fig 9b snapshots are unchanged.
"""
from __future__ import annotations

import copy

from process_bigraph import Process


def _f(d):
    return {"_type": "float", "_default": d}


def _chrom_dna(chrom, default=1.0):
    """The DNA amount on a chromosome node, whether it sits directly on the node
    (flattened) or nested under `contents`."""
    if "dna" in chrom:
        return chrom["dna"]
    contents = chrom.get("contents")
    if isinstance(contents, dict) and "dna" in contents:
        return contents["dna"]
    return default


def _chrom(dna=1.0):
    return {"_control": "chromosome", "contents": {"dna": dna}}


def _cell_chromosomes(cell):
    """(key, node) of every chromosome in a cell — under `contents` (canonical)
    or directly on the cell (a flattened shape)."""
    contents = cell.get("contents")
    src = contents if isinstance(contents, dict) else cell
    return [(k, v) for k, v in src.items()
            if not k.startswith("_") and isinstance(v, dict) and v.get("_control") == "chromosome"]


class CellCycleDivision(Process):
    """A REPEATING cell cycle over the colony place graph. Every `cycle` time
    units the colony alternates two genuine place-graph rewrites:

      REPLICATE — each cell holding one chromosome duplicates it (1 → 2 sisters).
      DIVIDE    — each cell holding two chromosomes splits into two daughters
                  (unique ids), partitioning one chromosome to each.

    Because both rewrites apply to EVERY cell each round, running it long keeps
    dividing: 1 → 2 → 4 → 8 … up to `capacity` cells (a cap so the tree stays
    finite). The first cycle is still segregate-then-divide, so the Fig 9b
    snapshots (one cell → replicated → divided) are unchanged."""
    config_schema = {"cycle": _f(3.0), "capacity": _f(16.0)}

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core)
        self._t = 0.0
        self._next = self.config["cycle"]
        self._phase = "replicate"     # alternates replicate <-> divide each round
        self._n = 0                   # unique daughter counter

    def inputs(self):
        return {"colony": "tree[node]"}

    def outputs(self):
        return {"colony": "overwrite[tree[node]]"}

    def update(self, state, interval):
        self._t += interval
        if self._t < self._next:
            return {}
        self._next += self.config["cycle"]
        colony = copy.deepcopy(state["colony"])
        cells = [(k, v) for k, v in colony.items()
                 if not k.startswith("_") and isinstance(v, dict) and v.get("_control") == "cell"]
        changed = False

        if self._phase == "replicate":
            for _, cell in cells:
                chroms = _cell_chromosomes(cell)
                if len(chroms) == 1:
                    dna = _chrom_dna(chroms[0][1])
                    cell["contents"] = {"chromosome_0": _chrom(dna), "chromosome_1": _chrom(dna)}
                    changed = True
            self._phase = "divide"
        else:  # divide — every cell with two sisters partitions into two daughters
            count = len(cells)
            cap = int(self.config["capacity"])
            for key, cell in cells:
                if count >= cap:
                    break
                chroms = _cell_chromosomes(cell)
                if len(chroms) >= 2:
                    del colony[key]
                    for i in range(2):
                        self._n += 1
                        colony[f"cell_{self._n}"] = {
                            "_control": "cell",
                            "contents": {"chromosome": _chrom(_chrom_dna(chroms[i][1]))}}
                    count += 1        # one cell became two → net +1
                    changed = True
            self._phase = "replicate"
        return {"colony": colony} if changed else {}


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
