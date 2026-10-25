"""Fig 11 · evolution — a *mechanistic* Wright–Fisher population with selection,
mutation, heritable variation, and ancestry.

This is the real-mechanism upgrade of ``fig11_topology`` (the ``PopulationEvolution``
place-graph toy, kept as the didactic baseline). The baseline runs ONE fixed seed
at carrying capacity 12, where — as the scientific review notes — drift dominates
and "the mean trait moving toward an imposed Gaussian optimum is expected by model
design". This variant answers that by making the population genetics quantitative
and testable:

* a real **Wright–Fisher** step at a large carrying capacity (default N=300):
  viability selection samples each generation's parents in proportion to fitness,
  offspring inherit the parent trait plus a Gaussian **mutation**, so variation,
  heritability and selection are explicit;
* **matched-null controls** are config switches (set with an epsilon, never 0.0,
  because bigraph_schema restores a float 0.0 config to its default): ``neutral``
  (sel_strength→0 ⇒ pure drift) and ``no_mutation`` (mut_sigma→0 ⇒ variance only
  erodes);
* **ancestry** is tracked (each individual's parent index per generation), so a
  lineage phylogeny can be drawn;
* fitness is either a prescribed **Gaussian** kernel on the trait–optimum distance
  (default) OR, optionally, **derived from an executable metabolic trait**
  (``fitness_mode="uptake"``): the trait is an uptake investment ``a``; growth is a
  saturating Michaelis–Menten uptake of a drifting resource minus a quadratic cost,
  ``g(a) = Vmax·a·R/(Km+a) − cost·a²``, whose interior optimum ``a*`` drifts with the
  resource — so the moving target is an emergent consequence of a metabolic
  tradeoff, not an imposed Gaussian.

The quantitative predictions the review asks for are theorems of this model:
the per-generation response obeys the **breeder's equation** R = h²·S (realized
heritability h²≈1 under clonal inheritance + mutation), the population tracks the
optimum with a **lag** that grows with the drift rate, and beyond a **critical
drift rate** the lag runs away and mean fitness collapses (an adaptation-failure /
evolutionary-rescue threshold). These are measured over MANY seeds with intervals —
one seed verifies reproducibility, not robustness.

``EvolvingPopulation`` is a plain NumPy engine (used directly by the tests and the
figure builder for many-seed ensembles, sweeps and phylogenies).
``PopulationGeneticsProcess`` wraps one run as a process-bigraph Process that emits
summary trajectories, so the composite demonstrates one seeded run through the
engine. Auto-registered at ``local:PopulationGeneticsProcess`` by ``build_core``.
"""
from __future__ import annotations

import numpy as np
from process_bigraph import Process


def _f(default):
    return {"_type": "float", "_default": default}


class EvolvingPopulation:
    """A Wright–Fisher population under viability selection toward a (possibly
    moving) optimum, with Gaussian mutation and explicit ancestry. Pure NumPy, so
    many independent replicates run cheaply.

    Parameters are plain floats/ints. ``neutral`` and ``no_mutation`` are the
    matched-null controls. ``fitness_mode`` is "gaussian" (prescribed kernel) or
    "uptake" (fitness derived from an executable metabolic tradeoff)."""

    def __init__(self, capacity=300, optimum0=0.0, drift=0.06, sel_strength=1.0,
                 mut_sigma=0.12, trait_mean0=0.0, trait_sd0=0.25, seed=0,
                 neutral=False, no_mutation=False, fitness_mode="gaussian",
                 vmax=2.0, km=1.0, cost=0.4, resource0=1.0):
        self.N = int(capacity)
        self.optimum0 = float(optimum0)
        self.drift = float(drift)
        self.sel = 0.0 if neutral else float(sel_strength)
        self.mut = 0.0 if no_mutation else float(mut_sigma)
        self.mode = fitness_mode
        self.vmax, self.km, self.cost, self.resource0 = map(float, (vmax, km, cost, resource0))
        self.rng = np.random.default_rng(int(seed))
        self.gen = 0
        self.traits = self.rng.normal(float(trait_mean0), float(trait_sd0), self.N)
        # ancestry: for a sampled set of lineages, remember the parent index each gen
        self.ancestry = []          # list of parent-index arrays (len N) per generation
        self._last_parents = None

    # ── fitness ────────────────────────────────────────────────────────────────
    def optimum(self, gen=None):
        g = self.gen if gen is None else gen
        if self.mode == "uptake":
            # the metabolically optimal uptake investment a* for the current resource
            R = self.resource0 + self.drift * g
            return self.vmax * R / (2.0 * self.cost * (self.km + R))
        return self.optimum0 + self.drift * g

    def fitness(self, traits):
        if self.mode == "uptake":
            R = self.resource0 + self.drift * self.gen
            a = np.maximum(traits, 0.0)
            g = self.vmax * a * R / (self.km + a) - self.cost * a * a   # net growth
            return np.exp(np.clip(g, -50, 50))                          # relative fitness ≥ 0
        opt = self.optimum()
        return np.exp(-self.sel * (traits - opt) ** 2)

    # ── one Wright–Fisher generation ────────────────────────────────────────────
    def step(self):
        w = self.fitness(self.traits)
        tot = w.sum()
        p = (w / tot) if tot > 0 else np.full(self.N, 1.0 / self.N)
        parents = self.rng.choice(self.N, size=self.N, p=p)            # viability selection
        self._last_parents = parents
        self.ancestry.append(parents.copy())
        offspring = self.traits[parents] + self.rng.normal(0.0, self.mut, self.N)
        self.traits = offspring
        self.gen += 1
        return self.traits

    def parent_offspring(self):
        """(parent_trait, offspring_trait) pairs for the realized-heritability
        regression (slope ≈ h²). Draws a fresh paired selection+mutation step from
        the current traits, so it is well-defined even before any ``step``."""
        pre = self.traits.copy()
        w = self.fitness(pre); p = w / w.sum()
        par = self.rng.choice(self.N, size=self.N, p=p)
        off = pre[par] + self.rng.normal(0.0, self.mut, self.N)
        return pre[par], off

    def run(self, generations):
        """Return per-generation history dict of arrays + trait snapshots."""
        hist = {"gen": [], "mean": [], "var": [], "optimum": [], "lag": [],
                "mean_fitness": [], "snapshots": [self.traits.copy()]}
        for _ in range(int(generations)):
            opt = self.optimum()
            hist["gen"].append(self.gen)
            hist["mean"].append(float(self.traits.mean()))
            hist["var"].append(float(self.traits.var()))
            hist["optimum"].append(float(opt))
            hist["lag"].append(float(abs(self.traits.mean() - opt)))
            hist["mean_fitness"].append(float(self.fitness(self.traits).mean()))
            self.step()
            hist["snapshots"].append(self.traits.copy())
        return hist


def ensemble(generations=40, n_seeds=30, **kw):
    """Run many independent replicates; return per-generation arrays of the mean
    trait and lag across seeds (shape [n_seeds, generations])."""
    means, lags, optima = [], [], []
    for s in range(int(n_seeds)):
        pop = EvolvingPopulation(seed=s, **kw)
        h = pop.run(generations)
        means.append(h["mean"]); lags.append(h["lag"]); optima = h["optimum"]
    return np.array(means), np.array(lags), np.array(optima)


class PopulationGeneticsProcess(Process):
    """Process-bigraph wrapper: steps one ``EvolvingPopulation`` one generation per
    ``generation`` interval and emits summary statistics (set-semantics) so the
    composite demonstrates a single seeded run through the engine. The full
    ensemble/phylogeny analysis is done directly on ``EvolvingPopulation``."""

    config_schema = {
        "generation": _f(1.0),
        "capacity": _f(300.0),
        "optimum0": _f(0.0),
        "drift": _f(0.06),
        "sel_strength": _f(1.0),
        "mut_sigma": _f(0.12),
        "trait_sd0": _f(0.25),
        "seed": {"_type": "integer", "_default": 0},
    }

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core)
        c = self.config
        self._pop = EvolvingPopulation(
            capacity=c["capacity"], optimum0=c["optimum0"], drift=c["drift"],
            sel_strength=c["sel_strength"], mut_sigma=c["mut_sigma"],
            trait_sd0=c["trait_sd0"], seed=int(c["seed"]))
        self._t = 0.0
        self._next = c["generation"]
        self._last = {}

    def inputs(self):
        return {}

    def outputs(self):
        return {"mean_trait": "float", "trait_var": "float", "optimum": "float",
                "lag": "float", "mean_fitness": "float", "pop_size": "float"}

    def _set(self, port, value):
        d = value - self._last.get(port, 0.0)
        self._last[port] = value
        return d

    def update(self, state, interval):
        self._t += interval
        if self._t < self._next:
            return {}
        self._next += self.config["generation"]
        opt = self._pop.optimum()
        mean = float(self._pop.traits.mean())
        out = {
            "mean_trait": self._set("mean_trait", mean),
            "trait_var": self._set("trait_var", float(self._pop.traits.var())),
            "optimum": self._set("optimum", float(opt)),
            "lag": self._set("lag", float(abs(mean - opt))),
            "mean_fitness": self._set("mean_fitness", float(self._pop.fitness(self._pop.traits).mean())),
            "pop_size": self._set("pop_size", float(self._pop.N)),
        }
        self._pop.step()
        return out
