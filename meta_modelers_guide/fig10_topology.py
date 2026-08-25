"""Fig 10.2 (biofilm) and 10.3 (evolution) as GENUINE place-graph rewrites — the
same runtime-topology approach as fig10_rewrite.py's division, so a viewer can
'run' the loom and watch the process-bigraph's structure change frame by frame.

Both act on a `tree[node]` store and return `overwrite[tree[node]]` so nodes
genuinely appear (and, for selection, disappear) at runtime:

  10.2 biofilm:  founder cell → colonizes (cells added) → secretes ECM (matrix
                 nodes added) → a structured multicellular community.
  10.3 evolution: a wildtype population → a fitter mutant appears → the mutant
                 lineage sweeps (mutants added, wildtype pruned by selection).

Nodes carry a Milner `_control` label ('cell'/'ecm', 'organism'/'mutant') so the
loom renders them as the right biological entity, and their contents under
`contents` (biomass / matrix / fitness) so each node shows a value.
"""
from __future__ import annotations

import copy

from process_bigraph import Process


def _f(d):
    return {"_type": "float", "_default": d}


def _top_nodes(tree, control):
    """Top-level child keys of a tree[node] store whose `_control` == control."""
    return [k for k, v in tree.items()
            if not k.startswith("_") and isinstance(v, dict) and v.get("_control") == control]


def _node(control, **contents):
    return {"_control": control, "contents": dict(contents)}


# ── 10.2 Biofilm development ────────────────────────────────────────────────
class BiofilmDevelopment(Process):
    """A founder cell attaches, COLONIZES (sibling cells are added one per
    `grow_every` up to `capacity`), then the mature community SECRETES ECM (a
    matrix node appears per cell). The `biofilm` place graph grows at runtime, so
    a viewer watches the community assemble node by node."""
    config_schema = {"grow_every": _f(2.0), "capacity": _f(5.0)}

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core)
        self._t = 0.0
        self._next = self.config["grow_every"]

    def inputs(self):
        return {"biofilm": "tree[node]"}

    def outputs(self):
        return {"biofilm": "overwrite[tree[node]]"}

    def update(self, state, interval):
        self._t += interval
        if self._t < self._next:
            return {}
        bf = copy.deepcopy(state["biofilm"])
        cells = _top_nodes(bf, "cell")
        ecm = _top_nodes(bf, "ecm")
        cap = int(self.config["capacity"])
        # Colonize: grow the population one cell at a time until carrying capacity.
        if len(cells) < cap:
            bf[f"cell_{len(cells)}"] = _node("cell", biomass=1.0)
            self._next += self.config["grow_every"]
            return {"biofilm": bf}
        # Mature: the full community secretes extracellular matrix (one node/cell).
        if len(ecm) < cap:
            bf[f"ecm_{len(ecm)}"] = _node("ecm", matrix=1.0)
            self._next += self.config["grow_every"]
            return {"biofilm": bf}
        return {}


def build_fig10_biofilm(grow_every: float = 2.0, capacity: float = 5.0, interval: float = 1.0):
    """Composite: a `biofilm` tree[node] holding one founder cell + the
    development process + a tree-preserving RAMEmitter (captures the whole
    subtree each tick so added nodes appear in the trajectory)."""
    return {"state": {
        "biofilm": {"_type": "tree[node]", "cell": _node("cell", biomass=1.0)},
        "development": {"_type": "process",
                        "address": "local:BiofilmDevelopment",
                        "interval": interval,
                        "config": {"grow_every": grow_every, "capacity": capacity},
                        "inputs": {"biofilm": ["biofilm"]},
                        "outputs": {"biofilm": ["biofilm"]}},
        "emitter": {"_type": "step", "address": "local:RAMEmitter",
                    "config": {"emit": {"biofilm": "tree[node]", "time": "float"}},
                    "inputs": {"biofilm": ["biofilm"], "time": ["global_time"]}},
    }}


# ── 10.2 Biofilm EMERGENCE from free motile bacteria ────────────────────────
class BiofilmEmergence(Process):
    """Biofilm formation from free-swimming bacteria as a place-graph rewrite.

    Free motile bacteria live as top-level siblings in the environment (each
    `_control: 'cell'` with `motile: 1`). Two runtime events reorganize the place
    graph:

      ATTACH  — the motile bacteria attach to the surface and AGGREGATE: they
                leave the top level and become children of a new `biofilm` node,
                switching `motile -> 0` (sessile). Dispersed siblings collapse
                into one nested microcolony.
      MATURE  — the sessile community secretes extracellular matrix: `ecm`
                (matrix) nodes appear INSIDE the biofilm, one per interval, until
                `ecm_count` — a structured, matrix-encased community.

    So running it turns dispersed free cells into a nested community and then a
    matrix-encased biofilm — the topology emerges, it is not pre-declared."""
    config_schema = {"attach_at": _f(2.0), "mature_at": _f(4.0), "ecm_count": _f(3.0)}

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core)
        self._t = 0.0
        self._attached = False
        self._ecm = 0

    def inputs(self):
        return {"env": "tree[node]"}

    def outputs(self):
        return {"env": "overwrite[tree[node]]"}

    def update(self, state, interval):
        self._t += interval
        env = copy.deepcopy(state["env"])
        # Attachment + aggregation: free motile bacteria nest into a biofilm microcolony.
        if not self._attached and self._t >= self.config["attach_at"]:
            free = _top_nodes(env, "cell")
            if free:
                cells = {}
                for i, k in enumerate(free):
                    biomass = env[k].get("contents", {}).get("biomass", 1.0)
                    cells[f"cell_{i}"] = _node("cell", biomass=biomass, motile=0.0)
                    del env[k]
                env["biofilm"] = {"_control": "biofilm", "contents": cells}
                self._attached = True
                return {"env": env}
        # Maturation: the sessile community secretes ECM (matrix) nodes into the biofilm.
        elif (self._attached and self._t >= self.config["mature_at"]
              and self._ecm < int(self.config["ecm_count"])):
            bf = env.get("biofilm")
            if isinstance(bf, dict):
                bf.setdefault("contents", {})[f"ecm_{self._ecm}"] = _node("ecm", matrix=1.0)
                self._ecm += 1
                return {"env": env}
        return {}


def build_fig10_biofilm_emergence(n_bacteria: int = 4, attach_at: float = 2.0,
                                  mature_at: float = 4.0, ecm_count: float = 3.0,
                                  interval: float = 1.0):
    """Composite: an `env` tree[node] holding a surface + N free motile bacteria,
    the emergence process, and a tree-preserving RAMEmitter (captures the whole
    subtree each tick so the reorganizing topology appears in the trajectory)."""
    env = {"_type": "tree[node]", "surface": _node("surface")}
    for i in range(int(n_bacteria)):
        env[f"bacterium_{i}"] = _node("cell", biomass=1.0, motile=1.0)
    return {"state": {
        "env": env,
        "emergence": {"_type": "process",
                      "address": "local:BiofilmEmergence",
                      "interval": interval,
                      "config": {"attach_at": attach_at, "mature_at": mature_at,
                                 "ecm_count": ecm_count},
                      "inputs": {"env": ["env"]},
                      "outputs": {"env": ["env"]}},
        "emitter": {"_type": "step", "address": "local:RAMEmitter",
                    "config": {"emit": {"env": "tree[node]", "time": "float"}},
                    "inputs": {"env": ["env"], "time": ["global_time"]}},
    }}


# ── 10.3 Evolution ──────────────────────────────────────────────────────────
class LineageEvolution(Process):
    """A population that EVOLVES its place graph. Early generations: the wildtype
    reproduces (organism nodes added). At `mutate_at`: a fitter MUTANT appears.
    Then a SELECTION sweep — each generation adds a mutant and prunes one wildtype
    — until the mutant lineage has taken over. Nodes are added AND removed at
    runtime, so a viewer watches the sweep play out."""
    config_schema = {"generation": _f(2.0), "mutate_at": _f(4.0),
                     "founders": _f(3.0), "capacity": _f(6.0)}

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core)
        self._t = 0.0
        self._next = self.config["generation"]

    def inputs(self):
        return {"population": "tree[node]"}

    def outputs(self):
        return {"population": "overwrite[tree[node]]"}

    def update(self, state, interval):
        self._t += interval
        if self._t < self._next:
            return {}
        self._next += self.config["generation"]
        pop = copy.deepcopy(state["population"])
        orgs = _top_nodes(pop, "organism")
        muts = _top_nodes(pop, "mutant")
        founders = int(self.config["founders"])
        cap = int(self.config["capacity"])

        # Phase 1 — the wildtype population establishes (before the mutation).
        if not muts and self._t < self.config["mutate_at"]:
            if len(orgs) < founders:
                pop[f"org_{len(orgs)}"] = _node("organism", fitness=1.0)
                return {"population": pop}
            return {}
        # A fitter variant arises, once.
        if not muts:
            pop["mut_0"] = _node("mutant", fitness=1.6)
            return {"population": pop}
        # Phase 2 — selection sweep: the mutant lineage grows, wildtype is pruned.
        if len(orgs) + len(muts) < cap and orgs:
            pop[f"mut_{len(muts)}"] = _node("mutant", fitness=1.6)
            del pop[orgs[-1]]
            return {"population": pop}
        if orgs:
            del pop[orgs[-1]]
            return {"population": pop}
        return {}


def build_fig10_evolution(generation: float = 2.0, mutate_at: float = 4.0,
                          founders: float = 3.0, capacity: float = 6.0, interval: float = 1.0):
    """Composite: a `population` tree[node] with one wildtype organism + the
    evolution process + a tree-preserving RAMEmitter."""
    return {"state": {
        "population": {"_type": "tree[node]", "organism": _node("organism", fitness=1.0)},
        "evolution": {"_type": "process",
                      "address": "local:LineageEvolution",
                      "interval": interval,
                      "config": {"generation": generation, "mutate_at": mutate_at,
                                 "founders": founders, "capacity": capacity},
                      "inputs": {"population": ["population"]},
                      "outputs": {"population": ["population"]}},
        "emitter": {"_type": "step", "address": "local:RAMEmitter",
                    "config": {"emit": {"population": "tree[node]", "time": "float"}},
                    "inputs": {"population": ["population"], "time": ["global_time"]}},
    }}
