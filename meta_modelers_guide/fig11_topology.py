"""Fig 11b — evolution as a genuine place-graph rewrite you can PLAY forward.

A ``population`` (typed ``tree[node]``) of ``cell`` nodes evolves under a
``environment`` whose ``selection_optimum`` DRIFTS over time. Every generation:

  1. the environment's optimum shifts (a *moving target*),
  2. each cell's ``replication_rate`` is re-scored by how close its heritable
     scalar ``trait`` sits to the current optimum (a Gaussian fitness kernel),
  3. the fitter cells reproduce — a daughter ``cell`` node is ADDED to the
     population, its ``trait`` inherited from the parent ± Gaussian *mutation*,
  4. the population is capped at ``capacity``.

Nodes are added at runtime and the optimum leaf changes each tick, so the loom's
topology-playback (``isTopoTraj``) animates the trait cloud chasing the moving
optimum: selection + mutation + reproduction, the minimal Darwinian loop.

Every cell shares ONE schema — ``{trait, replication_rate}`` under a ``cell``
control — unlike the old draft, which had two differently-shaped cell nodes.

Mirrors the runtime-rewrite pattern of :mod:`meta_modelers_guide.fig10_topology`
(``tree[node]`` in, ``overwrite[tree[node]]`` out, deep-copy-and-mutate in
``update``). Auto-registered at ``local:PopulationEvolution`` by ``build_core``.
"""
from __future__ import annotations

import copy
import math
import random

from process_bigraph import Process


def _f(d):
    return {"_type": "float", "_default": d}


def _top_nodes(tree, control):
    return [k for k, v in tree.items()
            if not k.startswith("_") and isinstance(v, dict) and v.get("_control") == control]


def _node(control, **contents):
    return {"_control": control, "contents": dict(contents)}


class PopulationEvolution(Process):
    """A population whose place graph evolves under a shifting environment.

    Reads + rewrites two ``tree[node]`` stores: ``population`` (grows as cells
    reproduce) and ``environment`` (its ``selection_optimum`` drifts). Selection
    re-scores each cell's replication rate; reproduction adds mutated daughters.
    """

    config_schema = {
        "generation": _f(1.0),     # time between division rounds
        "optimum0": _f(0.0),       # starting favored trait value
        "drift": _f(0.07),         # optimum shift per generation (slow moving target)
        "sel_strength": _f(0.6),   # Gaussian selection sharpness (fitness = e^{-s·Δ²})
        "mut_sigma": _f(0.28),     # sd of the heritable mutation step
        "div_rate": _f(0.35),      # per-generation division probability at perfect fitness
        "capacity": _f(12.0),      # population carrying capacity (node cap)
        "seed": {"_type": "integer", "_default": 1},
    }

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core)
        self._t = 0.0
        self._next = self.config["generation"]
        self._gen = 0
        self._n = 0  # monotonic daughter counter → unique node keys
        self._rng = random.Random(int(self.config["seed"]))

    def inputs(self):
        return {"population": "tree[node]", "environment": "tree[node]"}

    def outputs(self):
        return {"population": "overwrite[tree[node]]", "environment": "overwrite[tree[node]]"}

    def update(self, state, interval):
        self._t += interval
        if self._t < self._next:
            return {}
        self._next += self.config["generation"]
        self._gen += 1
        c = self.config

        pop = copy.deepcopy(state["population"])
        env = copy.deepcopy(state["environment"])

        # 1) the environment's optimum drifts — a moving target.
        niche_key = _top_nodes(env, "niche")[0]
        niche = env[niche_key]["contents"]
        optimum = float(c["optimum0"]) + float(c["drift"]) * self._gen
        niche["selection_optimum"] = round(optimum, 2)

        sel = float(c["sel_strength"])
        mut_sigma = float(c["mut_sigma"])
        div_rate = float(c["div_rate"])
        cap = int(c["capacity"])

        def fitness(trait):
            return math.exp(-sel * (trait - optimum) ** 2)

        # 2) selection re-scores each cell's division_rate by how close its trait
        #    sits to the current optimum.
        cells = _top_nodes(pop, "cell")
        for k in cells:
            contents = pop[k]["contents"]
            contents["division_rate"] = round(div_rate * fitness(float(contents.get("trait", 0.0))), 2)

        # 3) BINARY FISSION: a cell divides with probability div_rate·fitness — the
        #    fitter (nearer the optimum) divide sooner. On division the PARENT is
        #    REPLACED by two daughters, each inheriting its trait ± Gaussian
        #    mutation (so cell_0 does not persist once it has divided). Cells that
        #    don't divide survive unchanged, keeping their identity.
        changed = False
        for k in cells:
            trait = float(pop[k]["contents"].get("trait", 0.0))
            if self._rng.random() < div_rate * fitness(trait):
                del pop[k]  # parent consumed by its own division
                for _ in range(2):
                    self._n += 1
                    dt = trait + self._rng.gauss(0.0, mut_sigma)
                    pop[f"cell_{self._n}"] = _node(
                        "cell", trait=round(dt, 2),
                        division_rate=round(div_rate * fitness(dt), 2))
                changed = True

        # 4) death by selection: if the population overflows carrying capacity, the
        #    least-fit cells (furthest from the optimum) die — so the trait cloud
        #    keeps tracking the moving optimum rather than filling with laggards.
        live = _top_nodes(pop, "cell")
        if len(live) > cap:
            doomed = sorted(live, key=lambda k: abs(
                float(pop[k]["contents"].get("trait", 0.0)) - optimum), reverse=True)
            for k in doomed[:len(live) - cap]:
                del pop[k]
            changed = True

        # Guard against extinction (all cells happened to divide-and-die out): keep
        # at least the fittest daughter. (In practice capacity>1 prevents this.)
        if not _top_nodes(pop, "cell"):
            self._n += 1
            pop[f"cell_{self._n}"] = _node("cell", trait=round(optimum, 2), division_rate=round(div_rate, 2))
            changed = True

        # Return the environment every generation (optimum moved); the population
        # only when its topology actually changed.
        out = {"environment": env}
        if changed:
            out["population"] = pop
        return out


def build_fig11_population_evolution(
    generation: float = 1.0, optimum0: float = 0.0, drift: float = 0.07,
    sel_strength: float = 0.6, mut_sigma: float = 0.28, div_rate: float = 0.35,
    capacity: float = 12.0, seed: int = 1, interval: float = 1.0,
):
    """Composite: a founder ``population`` + a ``environment`` niche + the
    evolution process + a subtree-preserving RAMEmitter. Play it forward and the
    founder's lineage divides (binary fission — each parent replaced by two
    mutated daughters), grows to capacity, and the trait cloud tracks the slowly
    drifting selection optimum over many generations."""
    return {"state": {
        "population": {
            "_type": "tree[node]",
            "cell_0": _node("cell", trait=0.0, division_rate=div_rate),
        },
        "environment": {
            "_type": "tree[node]",
            "niche": _node("niche", selection_optimum=optimum0, resource=1.0),
        },
        "evolution": {
            "_type": "process",
            "address": "local:PopulationEvolution",
            "interval": interval,
            "config": {
                "generation": generation, "optimum0": optimum0, "drift": drift,
                "sel_strength": sel_strength, "mut_sigma": mut_sigma,
                "div_rate": div_rate, "capacity": capacity, "seed": seed,
            },
            "inputs": {"population": ["population"], "environment": ["environment"]},
            "outputs": {"population": ["population"], "environment": ["environment"]},
        },
        "emitter": {
            "_type": "step", "address": "local:RAMEmitter",
            "config": {"emit": {"population": "tree[node]",
                                "environment": "tree[node]", "time": "float"}},
            "inputs": {"population": ["population"], "environment": ["environment"],
                       "time": ["global_time"]},
        },
    }}
