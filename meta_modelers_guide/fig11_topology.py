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
        "generation": _f(1.0),     # time between reproduction events
        "optimum0": _f(0.0),       # starting favored trait value
        "drift": _f(0.2),          # optimum shift per generation (the moving target)
        "sel_strength": _f(0.45),  # Gaussian selection sharpness (fitness = e^{-s·Δ²})
        "mut_sigma": _f(0.55),     # sd of the heritable mutation step
        "repl_base": _f(1.0),      # base replication rate at perfect fitness
        "births": _f(3.0),         # reproduction events per generation
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

        # 2) selection re-scores every cell's replication rate by trait↔optimum fit.
        cells = _top_nodes(pop, "cell")
        scored = []
        for k in cells:
            contents = pop[k]["contents"]
            trait = float(contents.get("trait", 0.0))
            fit = math.exp(-float(c["sel_strength"]) * (trait - optimum) ** 2)
            contents["replication_rate"] = round(float(c["repl_base"]) * fit, 2)
            scored.append((k, trait, fit))

        # 3) reproduction (a Moran-style birth–death so the population keeps
        #    turning over after it fills): each generation, a few birth events —
        #    the parent is drawn fitness-weighted (selection), the daughter
        #    inherits its trait ± Gaussian mutation. While below capacity the
        #    population GROWS; at capacity, each birth evicts the least-fit cell
        #    (the one furthest from the optimum), so the trait cloud can keep
        #    tracking the moving optimum instead of freezing.
        cap = int(c["capacity"])
        mut_sigma = float(c["mut_sigma"])
        repl_base = float(c["repl_base"])
        total_fit = sum(f for _, _, f in scored) or 1e-9
        added = False
        for _ in range(int(round(float(c["births"])))):
            # fitness-weighted parent selection (roulette).
            r = self._rng.random() * total_fit
            acc = 0.0
            parent_trait, parent_fit = scored[-1][1], scored[-1][2]
            for _k, tr, f in scored:
                acc += f
                if r <= acc:
                    parent_trait, parent_fit = tr, f
                    break
            live = _top_nodes(pop, "cell")
            if len(live) >= cap and len(live) > 1:
                victim = max(live, key=lambda k: abs(
                    float(pop[k]["contents"].get("trait", 0.0)) - optimum))
                del pop[victim]
            self._n += 1
            daughter_trait = parent_trait + self._rng.gauss(0.0, mut_sigma)
            pop[f"cell_{self._n}"] = _node(
                "cell",
                trait=round(daughter_trait, 2),
                replication_rate=round(repl_base * parent_fit, 2),
            )
            added = True

        # Return the environment every generation (optimum moved); the population
        # only when it actually changed, so no-op ticks stay cheap.
        out = {"environment": env}
        if added:
            out["population"] = pop
        return out


def build_fig11_population_evolution(
    generation: float = 1.0, optimum0: float = 0.0, drift: float = 0.2,
    sel_strength: float = 0.45, mut_sigma: float = 0.55, repl_base: float = 1.0,
    births: float = 3.0, capacity: float = 12.0, seed: int = 1, interval: float = 1.0,
):
    """Composite: a founder ``population`` + a ``environment`` niche + the
    evolution process + a subtree-preserving RAMEmitter. Play it forward and the
    population grows while the trait cloud tracks the drifting optimum."""
    return {"state": {
        "population": {
            "_type": "tree[node]",
            "cell_0": _node("cell", trait=0.0, replication_rate=1.0),
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
                "repl_base": repl_base, "births": births,
                "capacity": capacity, "seed": seed,
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
