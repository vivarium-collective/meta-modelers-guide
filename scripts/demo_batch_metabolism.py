#!/usr/bin/env python
"""Flagship proof: Fig 6 'one interface, three mechanisms' as a CLOSED-LOOP batch
culture, run through the real process-bigraph engine.

The atlas's fig06 executables ran metabolism open-loop on a clamped constant
nutrient pool, so coarse/kinetic/FBA all degenerated to straight lines differing
only in slope. Here the substrate is CONSERVED — the metabolism process consumes
its own nutrient pool (dS/dt = -uptake), a finite bolus S0 — so each rate law
produces its characteristic signature:

  * coarse  (first-order uptake  ku·S)        -> exponential substrate drawdown
  * kinetic (Michaelis-Menten vmax·S/(km+S))  -> zero-order then knee (Monod batch)
  * FBA     (LP: min(scale·S, capacity))      -> capacity-limited plateau then elbow

Same interface (nutrients ⇒ biomass, +nutrient consumption), three conforming
handlers, three visibly different dynamics — the compositional claim, made
convincing. Runs each handler in a real Composite via the engine.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from process_bigraph import Process, Composite, gather_emitter_results

from viva_meta_modelers_guide.core import build_core

S0, DT, N = 10.0, 0.2, 70
YIELD = 0.5


def _f(d):
    return {"_type": "float", "_default": d}


class _BatchBase(Process):
    """Closed-loop metabolism: consumes its own nutrient pool. Outputs the biomass
    made AND the nutrient consumed (negative delta on the shared pool)."""
    config_schema = {"yield_": _f(YIELD)}

    def inputs(self):
        return {"nutrients": "chemical_flux"}

    def outputs(self):
        return {"biomass": "mass", "nutrients": "chemical_flux"}

    def uptake(self, s):  # mol substrate consumed per unit time
        raise NotImplementedError

    def update(self, state, interval):
        s = max(0.0, float(state.get("nutrients", 0.0)))
        u = min(self.uptake(s), s / interval)          # never consume more than present
        return {"biomass": self.config["yield_"] * u * interval,
                "nutrients": -u * interval}


class CoarseBatch(_BatchBase):
    """Lumped first-order uptake: uptake = ku·S."""
    config_schema = {**_BatchBase.config_schema, "ku": _f(0.55)}
    def uptake(self, s): return self.config["ku"] * s


class KineticBatch(_BatchBase):
    """Michaelis-Menten uptake: uptake = vmax·S/(km+S)."""
    config_schema = {**_BatchBase.config_schema, "vmax": _f(1.15), "km": _f(0.4)}
    def uptake(self, s):
        c = self.config
        return c["vmax"] * s / (c["km"] + s) if (c["km"] + s) else 0.0


class FBABatch(_BatchBase):
    """Real COBRApy LP: biomass flux = min(uptake bound from S, network capacity)."""
    config_schema = {**_BatchBase.config_schema, "scale": _f(1.0), "capacity": _f(0.9)}

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core)
        self._m = None

    def _build(self):
        from cobra import Model, Reaction, Metabolite
        m = Model("fig06_batch_fba")
        nut = Metabolite("nutrient_c", compartment="c")
        bio = Metabolite("biomass_c", compartment="c")
        ex = Reaction("EX_nutrient"); ex.add_metabolites({nut: 1}); ex.lower_bound = 0; ex.upper_bound = 0
        grow = Reaction("BIOMASS"); grow.add_metabolites({nut: -1, bio: 1})
        grow.lower_bound = 0; grow.upper_bound = self.config["capacity"]
        dm = Reaction("DM_biomass"); dm.add_metabolites({bio: -1}); dm.lower_bound = 0; dm.upper_bound = 1000
        m.add_reactions([ex, grow, dm]); m.objective = "BIOMASS"
        self._m = m

    def uptake(self, s):
        if self._m is None:
            self._build()
        self._m.reactions.EX_nutrient.upper_bound = max(0.0, self.config["scale"] * s)
        f = self._m.slim_optimize()
        return 0.0 if f != f else float(f)


HANDLERS = [("coarse (first-order)", CoarseBatch, "#0d6e6b"),
            ("kinetic (Michaelis–Menten)", KineticBatch, "#a5620f"),
            ("FBA (COBRApy LP)", FBABatch, "#3f9e99")]


def run_one(cls):
    core = build_core()
    core.register_link(cls.__name__, cls)
    state = {
        "pool": {"nutrients": {"_type": "chemical_flux", "_default": S0},
                 "biomass": {"_type": "mass", "_default": 0.0}},
        "metabolism": {"_type": "process", "address": f"local:{cls.__name__}",
                       "config": {}, "interval": DT,
                       "inputs": {"nutrients": ["pool", "nutrients"]},
                       "outputs": {"biomass": ["pool", "biomass"],
                                   "nutrients": ["pool", "nutrients"]}},
        "emitter": {"_type": "step", "address": "local:RAMEmitter",
                    "config": {"emit": {"nutrients": "float", "biomass": "float", "time": "float"}},
                    "inputs": {"nutrients": ["pool", "nutrients"],
                               "biomass": ["pool", "biomass"], "time": ["global_time"]}},
    }
    sim = Composite({"state": state}, core=core)
    sim.run(N * DT)
    rows = gather_emitter_results(sim)[("emitter",)]
    t = [r["time"] for r in rows]
    return t, [r["nutrients"] for r in rows], [r["biomass"] for r in rows]


def main():
    fig, (axS, axB) = plt.subplots(1, 2, figsize=(9.2, 3.6), dpi=110)
    summary = []
    for label, cls, color in HANDLERS:
        t, S, B = run_one(cls)
        axS.plot(t, S, lw=2.2, color=color, label=label)
        axB.plot(t, B, lw=2.2, color=color, label=label)
        # time to exhaust 90% of substrate
        thr = next((tt for tt, s in zip(t, S) if s <= 0.1 * S0), t[-1])
        summary.append(f"{label:28s} final biomass {B[-1]:.2f}, 90%-substrate-consumed at t={thr:.1f}")
    for ax, ttl, yl in ((axS, "Substrate S(t) — batch drawdown", "nutrient pool"),
                        (axB, "Biomass B(t)", "biomass")):
        ax.set_title(ttl, fontsize=10, color="#16211f")
        ax.set_xlabel("time"); ax.set_ylabel(yl)
        ax.grid(True, alpha=0.15)
        for s in ("top", "right"): ax.spines[s].set_visible(False)
    axS.legend(fontsize=7.5, frameon=False)
    fig.suptitle("Fig 6 · one interface, three mechanisms — CLOSED-LOOP batch culture "
                 f"(S₀={S0:g}, conserved substrate)", fontsize=11, color="#0d6e6b")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    out = "scripts/_catalog/fig06_batch_demo"
    fig.savefig(out + ".svg", format="svg"); fig.savefig(out + ".png", format="png")
    print("\n".join(summary))
    print(f"\nwrote {out}.svg / .png")


if __name__ == "__main__":
    main()
