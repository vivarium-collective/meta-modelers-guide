"""Phase 4 · the whole cell — compose the atlas's figures into one running cell.

The figures compile in isolation; the paper's thesis is that they *compose*. This
module wires the recurring patterns into a single multiscale executable and closes
the paper's full arc in one run:

    interface (Fig 4)  →  cell–environment coupling (Fig 5)  →  metabolism (Fig 6)
        →  viability bounds (Fig 4)  →  rewrite: division (Fig 10) or disintegration (Fig 6)

A :class:`ViabilityMonitor` reads the cell's interface (temperature, biomass) and
sets its viability and two event flags. Metabolism is *gated by viability*, so when
the thermal environment leaves the viable band the cell stops growing, viability
collapses, and the disintegration event turns biomass into molecular debris (the
cell→molecular transition of Fig 6). Before that, once biomass crosses a threshold,
the division event partitions it into two daughters (Fig 10).

Every process is an ordinary process-bigraph :class:`Process`, auto-registered at
``local:<ClassName>`` by build_core. :func:`build_whole_cell` assembles them into a
cell-in-environment place graph with a RAM emitter, so the whole arc is one
trajectory. This is an *assembled* executable (a composition of the figures'
mechanisms), not a paper-figure compilation — see build_whole_cell.
"""
from __future__ import annotations

from process_bigraph import Process


def _f(default):
    return {"_type": "float", "_default": default}


class ThermalEnvironment(Process):
    """Drives the environmental temperature: a baseline, then a thermal shock after
    ``shock_time`` — the perturbation that pushes the cell past its viability bound."""
    config_schema = {"temp_normal": _f(37.0), "temp_shock": _f(50.0), "shock_time": _f(12.0)}

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core)
        self._clock = 0.0
        # the temperature store is initialised to temp_normal, so start _last there
        # (set-semantics deltas carry the store, not add on top of its initial value).
        self._last = self.config["temp_normal"]

    def inputs(self):
        return {}

    def outputs(self):
        return {"temperature": "temperature"}

    def update(self, state, interval):
        self._clock += interval
        c = self.config
        temp = c["temp_shock"] if self._clock >= c["shock_time"] else c["temp_normal"]
        d = temp - self._last
        self._last = temp
        return {"temperature": d}


class Uptake(Process):
    """Cell–environment coupling (Fig 5): import nutrients from the environment
    reservoir into the cell's local pool: d[local]/dt = k · nutrients_ext."""
    config_schema = {"uptake_rate": _f(0.5)}

    def inputs(self):
        return {"nutrients_ext": "concentration"}

    def outputs(self):
        return {"nutrients_local": "concentration"}

    def update(self, state, interval):
        ext = float(state.get("nutrients_ext", 0.0))
        return {"nutrients_local": self.config["uptake_rate"] * ext * interval}


class ViabilityGatedMetabolism(Process):
    """Metabolism (Fig 6) gated by viability — and the whole cell's mechanism-swap
    slot. ``mode`` selects which of the Fig 6 metabolism kinetics grows the cell,
    behind the SAME ports (``nutrients_local, viability`` → ``biomass, energy,
    nutrients_local``):

      * ``coarse``  — lumped first-order growth (rate ``k · nutrients_local``),
      * ``kinetic`` — saturating Michaelis–Menten growth (``vmax · n /(km+n)``),
      * ``fba``     — genome-scale flux-balance growth via the real Fig 6 COBRApy
        ``e_coli_core`` solver (delegates to ``FBAMetabolism``).

    Growth is scaled by viability (``× v``) so it halts when the cell leaves its
    tolerance band. Swapping ``mode`` swaps the mechanism at the WHOLE-CELL level
    — the paper's handler-independence thesis (Fig 6 law 4), now at the capstone:
    the three kinetics give three distinct life histories behind one interface."""
    config_schema = {"mode": {"_type": "string", "_default": "coarse"},
                     "k": _f(0.6), "vmax": _f(1.4), "km": _f(0.4),
                     "energy_yield": _f(0.4)}

    def inputs(self):
        return {"nutrients_local": "concentration", "viability": "viability"}

    def outputs(self):
        return {"biomass": "mass", "energy": "energy", "nutrients_local": "concentration"}

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core)
        self._fba = None
        if (self.config.get("mode") or "coarse") == "fba":
            from .handlers_fig05_fba import FBAMetabolism
            self._fba = FBAMetabolism({}, core=core)

    def _growth_rate(self, nut: float) -> float:
        """Biomass growth rate at local nutrient ``nut`` under the selected Fig 6
        mechanism. Same input, three kinetics — the swap."""
        c = self.config
        mode = c.get("mode") or "coarse"
        if mode == "kinetic":
            denom = c["km"] + nut
            return (c["vmax"] * nut / denom) if denom else 0.0
        if mode == "fba" and self._fba is not None:
            # FBAMetabolism returns biomass=growth·interval; call with interval=1
            # to read the objective-value growth rate for this nutrient level.
            return float(self._fba.update({"nutrients": nut}, 1.0).get("biomass", 0.0))
        return c["k"] * nut  # coarse (lumped first-order)

    def update(self, state, interval):
        nut = float(state.get("nutrients_local", 0.0))
        v = float(state.get("viability", 0.0))
        g = self._growth_rate(nut) * v
        return {"biomass": g * interval,
                "energy": self.config["energy_yield"] * g * interval,
                "nutrients_local": -g * interval}


class ViabilityMonitor(Process):
    """The interface's viability logic (Fig 4). Relaxes viability toward 1 inside the
    thermal tolerance band and toward 0 outside it, and raises two event flags:
    ``dividing`` when biomass crosses the division threshold while healthy, and
    ``disintegrating`` when viability falls below the survival floor."""
    config_schema = {
        "temp_opt": _f(37.0), "temp_tol": _f(5.0), "relax": _f(0.5),
        "division_threshold": _f(1.0), "viability_floor": _f(0.3),
    }

    def inputs(self):
        return {"temperature": "temperature", "biomass": "mass", "viability": "viability"}

    def outputs(self):
        return {"viability": "viability", "dividing": "fraction", "disintegrating": "fraction"}

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core)
        self._last_div = 0.0
        self._last_dis = 0.0

    def _set(self, attr, value):
        delta = value - getattr(self, attr)
        setattr(self, attr, value)
        return delta

    def update(self, state, interval):
        c = self.config
        temp = float(state.get("temperature", c["temp_opt"]))
        biomass = float(state.get("biomass", 0.0))
        v = float(state.get("viability", 0.0))
        in_band = abs(temp - c["temp_opt"]) <= c["temp_tol"]
        d_via = c["relax"] * ((1.0 if in_band else 0.0) - v) * interval
        v_next = v + d_via
        dividing = 1.0 if (biomass >= c["division_threshold"] and v_next > 0.8) else 0.0
        disintegrating = 1.0 if v_next < c["viability_floor"] else 0.0
        return {"viability": d_via,
                "dividing": self._set("_last_div", dividing),
                "disintegrating": self._set("_last_dis", disintegrating)}


class DivisionEvent(Process):
    """Rewrite (Fig 10): on the ``dividing`` flag, PARTITION the mother's biomass
    into two daughters ONCE and increment the cell count. Mass is conserved — the
    mother's own ``biomass`` is decremented by exactly what the daughters receive
    (mother M → the focal cell keeps M/2, a sibling daughter gets M/2), so total
    biomass across {cell, daughter} is unchanged by division."""
    config_schema = {}

    def inputs(self):
        return {"biomass": "mass", "dividing": "fraction"}

    def outputs(self):
        # `biomass` writes back to the mother (cell) store so the partition
        # conserves mass; `biomass_1` seeds the sibling daughter.
        return {"biomass": "mass", "biomass_1": "mass", "cell_count": "cell_count"}

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core)
        self._done = False

    def update(self, state, interval):
        if self._done or float(state.get("dividing", 0.0)) < 0.5:
            return {}
        self._done = True
        half = float(state.get("biomass", 0.0)) / 2.0
        # mother loses half (→ M/2); the sibling daughter gains that half. Conserved.
        return {"biomass": -half, "biomass_1": half, "cell_count": 1.0}


class DisintegrationEvent(Process):
    """Rewrite (Fig 6): on the ``disintegrating`` flag, the maintained boundary
    fails — biomass decays into molecular debris (cell → molecular components)."""
    config_schema = {"decay_rate": _f(0.4)}

    def inputs(self):
        return {"biomass": "mass", "disintegrating": "fraction"}

    def outputs(self):
        return {"biomass": "mass", "debris": "concentration"}

    def update(self, state, interval):
        if float(state.get("disintegrating", 0.0)) < 0.5:
            return {}
        biomass = float(state.get("biomass", 0.0))
        loss = self.config["decay_rate"] * biomass * interval
        return {"biomass": -loss, "debris": loss}


# ── assemble the whole cell ───────────────────────────────────────────────────
def build_whole_cell(emit: bool = True, metabolism: str = "coarse") -> dict:
    """A cell-in-environment composite wiring the figures' mechanisms together.

    ``metabolism`` selects which Fig 6 metabolism mechanism grows the cell —
    ``"coarse"`` | ``"kinetic"`` | ``"fba"`` — behind identical ports. Building the
    whole cell three times with the three values, and running each, is the
    capstone demonstration of handler independence (Fig 6 law 4) at the whole-cell
    level: same composed cell, three metabolic mechanisms, three life histories.

    Place graph: ``environment{nutrients, temperature}`` and
    ``cell{biomass, energy, viability, nutrients_local, dividing, disintegrating,
    debris}`` with two pre-declared ``daughter`` compartments and a top-level
    ``cell_count`` — the same pattern the Fig 10 composites use.
    """
    def proc(address, inputs, outputs, config=None, interval=0.1):
        return {"_type": "process", "address": f"local:{address}",
                "config": config or {}, "interval": interval,
                "inputs": inputs, "outputs": outputs}

    state: dict = {
        "environment": {
            "nutrients": {"_type": "concentration", "_default": 1.0},
            "temperature": {"_type": "temperature", "_default": 37.0},
        },
        "cell": {
            "biomass": {"_type": "mass", "_default": 0.3},
            "energy": {"_type": "energy", "_default": 0.0},
            "viability": {"_type": "viability", "_default": 1.0},
            "nutrients_local": {"_type": "concentration", "_default": 0.0},
            "dividing": {"_type": "fraction", "_default": 0.0},
            "disintegrating": {"_type": "fraction", "_default": 0.0},
            "debris": {"_type": "concentration", "_default": 0.0},
        },
        "daughter_1": {"biomass": {"_type": "mass", "_default": 0.0}},
        "daughter_2": {"biomass": {"_type": "mass", "_default": 0.0}},
        "cell_count": {"_type": "cell_count", "_default": 1.0},

        "thermal": proc("ThermalEnvironment",
                        {}, {"temperature": ["environment", "temperature"]},
                        {"temp_normal": 37.0, "temp_shock": 50.0, "shock_time": 12.0}),
        "uptake": proc("Uptake",
                       {"nutrients_ext": ["environment", "nutrients"]},
                       {"nutrients_local": ["cell", "nutrients_local"]},
                       {"uptake_rate": 0.5}),
        "metabolism": proc("ViabilityGatedMetabolism",
                           {"nutrients_local": ["cell", "nutrients_local"],
                            "viability": ["cell", "viability"]},
                           {"biomass": ["cell", "biomass"], "energy": ["cell", "energy"],
                            "nutrients_local": ["cell", "nutrients_local"]},
                           {"mode": metabolism, "k": 0.6, "vmax": 1.4, "km": 0.4,
                            "energy_yield": 0.4}),
        "monitor": proc("ViabilityMonitor",
                        {"temperature": ["environment", "temperature"],
                         "biomass": ["cell", "biomass"], "viability": ["cell", "viability"]},
                        {"viability": ["cell", "viability"],
                         "dividing": ["cell", "dividing"],
                         "disintegrating": ["cell", "disintegrating"]},
                        {"temp_opt": 37.0, "temp_tol": 5.0, "relax": 0.5,
                         "division_threshold": 1.0, "viability_floor": 0.3}),
        "division": proc("DivisionEvent",
                         {"biomass": ["cell", "biomass"], "dividing": ["cell", "dividing"]},
                         {"biomass": ["cell", "biomass"],            # mother, decremented (conserved)
                          "biomass_1": ["daughter_1", "biomass"],    # sibling daughter
                          "cell_count": ["cell_count"]}),
        "disintegration": proc("DisintegrationEvent",
                               {"biomass": ["cell", "biomass"],
                                "disintegrating": ["cell", "disintegrating"]},
                               {"biomass": ["cell", "biomass"], "debris": ["cell", "debris"]},
                               {"decay_rate": 0.4}),
    }
    if emit:
        state["emitter"] = {
            "_type": "step", "address": "local:RAMEmitter",
            "config": {"emit": {"biomass": "mass", "viability": "viability",
                                "temperature": "temperature", "cell_count": "cell_count",
                                "debris": "concentration", "time": "float"}},
            "inputs": {"biomass": ["cell", "biomass"], "viability": ["cell", "viability"],
                       "temperature": ["environment", "temperature"],
                       "cell_count": ["cell_count"], "debris": ["cell", "debris"],
                       "time": ["global_time"]},
        }
    return {"state": state}


def build_disintegration(emit: bool = True) -> dict:
    """A FOCUSED, PLAYABLE disintegration composite (Fig 6a): thermal shock →
    viability collapse → cell-level metabolism halts → biomass decays into molecular
    debris. No division — the trajectory reads as the pure cell→molecular level
    shift. Assembled in the figures' style (like build_whole_cell), not compiler-
    emitted; its RAM emitter makes the collapse visible frame-by-frame in the loom.
    """
    def proc(address, inputs, outputs, config=None):
        return {"_type": "process", "address": f"local:{address}",
                "config": config or {}, "interval": 1.0,
                "inputs": inputs, "outputs": outputs}

    state: dict = {
        "environment": {
            "nutrients": {"_type": "concentration", "_default": 1.0},
            "temperature": {"_type": "temperature", "_default": 37.0},
        },
        "cell": {
            "biomass": {"_type": "mass", "_default": 0.3},
            "energy": {"_type": "energy", "_default": 0.0},
            "viability": {"_type": "viability", "_default": 1.0},
            "nutrients_local": {"_type": "concentration", "_default": 0.0},
            "dividing": {"_type": "fraction", "_default": 0.0},
            "disintegrating": {"_type": "fraction", "_default": 0.0},
            "debris": {"_type": "concentration", "_default": 0.0},
        },
        "thermal": proc("ThermalEnvironment", {},
                        {"temperature": ["environment", "temperature"]},
                        {"temp_normal": 37.0, "temp_shock": 50.0, "shock_time": 8.0}),
        "uptake": proc("Uptake",
                       {"nutrients_ext": ["environment", "nutrients"]},
                       {"nutrients_local": ["cell", "nutrients_local"]},
                       {"uptake_rate": 0.5}),
        "metabolism": proc("ViabilityGatedMetabolism",
                           {"nutrients_local": ["cell", "nutrients_local"],
                            "viability": ["cell", "viability"]},
                           {"biomass": ["cell", "biomass"], "energy": ["cell", "energy"],
                            "nutrients_local": ["cell", "nutrients_local"]},
                           {"mode": "coarse", "k": 0.6, "energy_yield": 0.4}),
        "monitor": proc("ViabilityMonitor",
                        {"temperature": ["environment", "temperature"],
                         "biomass": ["cell", "biomass"], "viability": ["cell", "viability"]},
                        {"viability": ["cell", "viability"],
                         "dividing": ["cell", "dividing"],
                         "disintegrating": ["cell", "disintegrating"]},
                        {"temp_opt": 37.0, "temp_tol": 5.0, "relax": 0.5,
                         "division_threshold": 1e9, "viability_floor": 0.5}),
        "disintegration": proc("DisintegrationEvent",
                               {"biomass": ["cell", "biomass"],
                                "disintegrating": ["cell", "disintegrating"]},
                               {"biomass": ["cell", "biomass"], "debris": ["cell", "debris"]},
                               {"decay_rate": 0.4}),
    }
    if emit:
        state["emitter"] = {
            "_type": "step", "address": "local:RAMEmitter",
            "config": {"emit": {"biomass": "mass", "viability": "viability",
                                "temperature": "temperature", "debris": "concentration",
                                "disintegrating": "fraction", "time": "float"}},
            "inputs": {"biomass": ["cell", "biomass"], "viability": ["cell", "viability"],
                       "temperature": ["environment", "temperature"],
                       "debris": ["cell", "debris"],
                       "disintegrating": ["cell", "disintegrating"],
                       "time": ["global_time"]},
        }
    return {"state": state}
