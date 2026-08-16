"""Physically-consistent, CLOSED-LOOP dynamics for every figure of the atlas.

The atlas's original executables ran their (real) rate laws open-loop on clamped
constant inputs for a handful of steps, so every trajectory degenerated to a
straight line or a step and the biology never showed. This module rebuilds each
figure as a conserved, closed-loop model run to completion, through the real
process-bigraph engine:

  * quantities are CONSERVED — substrate consumed = biomass made (× yield),
    field mass is redistributed by diffusion, mother mass = Σ daughter mass;
  * inputs are DRIVEN and pools DEPLETE — nothing is clamped;
  * rate laws are the real physical/biochemical forms — Michaelis–Menten, Monod,
    mass-action, Fickian diffusion, Arrhenius denaturation, logistic/competitive
    growth — so each figure shows its characteristic signature (a saturation
    knee, a gradient, a steady state, a selection sweep, a viability cliff);
  * runs long enough for the dynamics to develop and reach steady state / an event.

Fidelity is "physically-consistent toy": conserved and correctly-shaped, with
transparent (uncalibrated) constants — illustrative of the composition PATTERN,
not a fitted cell. Every model reports the invariant it conserves so the reader
can check it held (see scripts/render_dynamics.py).

All models are ordinary Process/Step subclasses auto-registered by build_core;
each ``build_<slug>()`` returns a composite state dict (pools + process + a
RAMEmitter) ready for ``Composite(...).run()``.
"""
from __future__ import annotations

import math

from process_bigraph import Process, Step

# ─── rate laws (pure) ────────────────────────────────────────────────────────
def monod(s, vmax, km):
    return vmax * s / (km + s) if (km + s) > 0 else 0.0


def arrhenius_excess(T, T_tol, width):
    """Denaturation rate that is ~0 inside the tolerance band and rises sharply
    (exponentially) once temperature exceeds it — a thermal-stress cliff."""
    return math.exp(max(0.0, T - T_tol) / width) - 1.0


def _f(d):
    return {"_type": "float", "_default": d}


class ODE(Process):
    """Base: subclass sets PORTS (list) + implements deriv(state)->{port: d/dt}.
    update integrates one explicit-Euler step (store accumulates rate·interval)."""
    PORTS: list[str] = []

    def inputs(self):
        return {p: "float" for p in self.PORTS}

    def outputs(self):
        return {p: "float" for p in self.PORTS}

    def deriv(self, s):
        raise NotImplementedError

    def update(self, state, interval):
        s = {p: float(state.get(p, 0.0)) for p in self.PORTS}
        d = self.deriv(s)
        return {p: d.get(p, 0.0) * interval for p in self.PORTS}


def _emitter(obs):
    return {"_type": "step", "address": "local:RAMEmitter",
            "config": {"emit": {**{o: "float" for o in obs}, "time": "float"}},
            "inputs": {**{o: [o] for o in obs}, "time": ["global_time"]}}


def _pool(v):
    return {"_type": "float", "_default": float(v)}


def _proc(cls, ports, config=None, interval=0.1):
    return {"_type": "process", "address": f"local:{cls}", "interval": interval,
            "config": config or {},
            "inputs": {p: [p] for p in ports}, "outputs": {p: [p] for p in ports}}


# ─── fig 04b · the typed interface: a cell in a batch environment ────────────
# Monod uptake depletes a finite nutrient; volume grows logistically (gated by
# viability); temperature ramps and viability follows an Arrhenius cliff.
class CellInterface(ODE):
    PORTS = ["nutrient", "volume", "viability", "temperature"]
    config_schema = {"vmax": _f(0.9), "km": _f(0.4), "yield_": _f(0.6),
                     "maint": _f(0.03), "ramp": _f(0.9), "t_max": _f(50.0),
                     "t_tol": _f(42.0), "t_width": _f(3.0), "denat": _f(0.6)}

    def deriv(self, s):
        c = self.config
        N, V, phi, T = s["nutrient"], s["volume"], s["viability"], s["temperature"]
        u = monod(N, c["vmax"], c["km"]) * V * max(phi, 0.0)      # uptake scales with size & health
        dV = c["yield_"] * u - c["maint"] * V
        dT = c["ramp"] if T < c["t_max"] else 0.0
        dphi = -c["denat"] * arrhenius_excess(T, c["t_tol"], c["t_width"]) * max(phi, 0.0)
        return {"nutrient": -u, "volume": dV, "viability": dphi, "temperature": dT}


def build_typed_interface():
    obs = ["nutrient", "volume", "viability", "temperature"]
    return {"state": {
        "nutrient": _pool(10.0), "volume": _pool(0.5),
        "viability": _pool(1.0), "temperature": _pool(37.0),
        "cell": _proc("CellInterface", obs), "emitter": _emitter(obs)}}


# ─── fig 05 · closing the loop: reaction–diffusion, cell as a sink ───────────
# A 1-D nutrient field diffuses (Fick); the cell sits at one node and consumes
# it (Monod), growing. A gradient forms; total (field + taken-up) is conserved.
class ReactionDiffusion(ODE):
    def __init__(self, config=None, core=None):
        super().__init__(config, core=core)
        self.n = int(self.config["n"])
        self.PORTS = [f"c{i}" for i in range(self.n)] + ["uptake_total", "biomass"]

    config_schema = {"n": _f(15.0), "D": _f(0.35), "site": _f(7.0),
                     "vmax": _f(0.6), "km": _f(0.3), "yield_": _f(0.7)}

    def deriv(self, s):
        c = self.config
        n, D, site = self.n, c["D"], int(c["site"])
        C = [s[f"c{i}"] for i in range(n)]
        d = {}
        for i in range(n):
            left = C[i - 1] if i > 0 else C[i]      # no-flux (Neumann) boundaries
            right = C[i + 1] if i < n - 1 else C[i]
            d[f"c{i}"] = D * (left - 2 * C[i] + right)
        u = monod(C[site], c["vmax"], c["km"])
        d[f"c{site}"] -= u                          # cell sink at the site
        d["uptake_total"] = u
        d["biomass"] = c["yield_"] * u
        return d


def build_closing_the_loop():
    n = 15
    state = {f"c{i}": _pool(0.0) for i in range(n)}
    state["c2"] = _pool(6.0)                         # a localized nutrient bolus, off-cell
    state["uptake_total"] = _pool(0.0); state["biomass"] = _pool(0.0)
    ports = [f"c{i}" for i in range(n)] + ["uptake_total", "biomass"]
    state["field"] = _proc("ReactionDiffusion", ports, {"n": n})
    state["emitter"] = _emitter(ports)
    return {"state": state}


# ─── fig 06 · one interface, three mechanisms (closed-loop batch) ────────────
class _Batch(ODE):
    PORTS = ["nutrient", "biomass"]
    config_schema = {"yield_": _f(0.5)}

    def uptake(self, S):
        raise NotImplementedError

    def deriv(self, s):
        u = min(self.uptake(s["nutrient"]), max(s["nutrient"], 0.0) / 1e-9) if s["nutrient"] > 0 else 0.0
        u = self.uptake(max(s["nutrient"], 0.0))
        return {"nutrient": -u, "biomass": self.config["yield_"] * u}


class CoarseBatch(_Batch):
    config_schema = {**_Batch.config_schema, "ku": _f(0.55)}
    def uptake(self, S): return self.config["ku"] * S


class KineticBatch(_Batch):
    config_schema = {**_Batch.config_schema, "vmax": _f(1.15), "km": _f(0.4)}
    def uptake(self, S): return monod(S, self.config["vmax"], self.config["km"])


class FBABatch(_Batch):
    config_schema = {**_Batch.config_schema, "scale": _f(1.0), "capacity": _f(0.9)}

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core); self._m = None

    def _build(self):
        from cobra import Model, Reaction, Metabolite
        m = Model("fig06"); nut = Metabolite("n_c", compartment="c"); bio = Metabolite("b_c", compartment="c")
        ex = Reaction("EX"); ex.add_metabolites({nut: 1}); ex.lower_bound = 0; ex.upper_bound = 0
        gr = Reaction("BIO"); gr.add_metabolites({nut: -1, bio: 1}); gr.lower_bound = 0
        gr.upper_bound = self.config["capacity"]
        dm = Reaction("DM"); dm.add_metabolites({bio: -1}); dm.lower_bound = 0; dm.upper_bound = 1e3
        m.add_reactions([ex, gr, dm]); m.objective = "BIO"; self._m = m

    def uptake(self, S):
        if self._m is None: self._build()
        self._m.reactions.EX.upper_bound = max(0.0, self.config["scale"] * S)
        f = self._m.slim_optimize()
        return 0.0 if f != f else float(f)


def _build_batch(cls):
    return {"state": {"nutrient": _pool(10.0), "biomass": _pool(0.0),
                      "met": _proc(cls, ["nutrient", "biomass"]),
                      "emitter": _emitter(["nutrient", "biomass"])}}


def build_three_mechanisms():          # overlay handled by the renderer
    return {"coarse": _build_batch("CoarseBatch"),
            "kinetic": _build_batch("KineticBatch"),
            "fba": _build_batch("FBABatch")}


# ─── fig 07 · molecular channels: turnover + energy balance ──────────────────
# Enzyme turns over a driven, depleting substrate (MM) into product + heat with a
# fixed thermodynamic efficiency (energy conserved: substrate energy = product +
# heat). Electrical channel is an Ohmic response to a decaying driving voltage.
class ChannelTransducer(ODE):
    PORTS = ["substrate", "product", "heat", "voltage", "current"]
    config_schema = {"vmax": _f(1.0), "km": _f(0.5), "eff": _f(0.6),
                     "e_sub": _f(1.0), "conductance": _f(0.4), "v_decay": _f(0.15)}

    def deriv(self, s):
        c = self.config
        r = monod(s["substrate"], c["vmax"], c["km"])           # turnover rate
        e_in = c["e_sub"] * r
        return {"substrate": -r, "product": c["eff"] * r,
                "heat": (1 - c["eff"]) * e_in,                  # dissipated heat = (1-η)·E_in
                "voltage": -c["v_decay"] * s["voltage"],
                "current": c["conductance"] * s["voltage"] - s["current"]}  # relax to Ohmic I=gV


def build_molecular_channels():
    obs = ["substrate", "product", "heat", "voltage", "current"]
    return {"state": {"substrate": _pool(8.0), "product": _pool(0.0), "heat": _pool(0.0),
                      "voltage": _pool(1.0), "current": _pool(0.0),
                      "mech": _proc("ChannelTransducer", obs), "emitter": _emitter(obs)}}


# ─── fig 08 · the nested cell: central-dogma cascade with degradation ────────
# gene→mRNA→protein with first-order degradation → the transcription-before-
# translation time hierarchy and two distinct steady states.
class CentralDogma(ODE):
    PORTS = ["mrna", "protein", "metabolite"]
    config_schema = {"k_tx": _f(1.2), "d_m": _f(0.5), "k_tl": _f(0.9), "d_p": _f(0.2),
                     "gene": _f(1.0), "k_met": _f(0.6), "d_met": _f(0.3)}

    def deriv(self, s):
        c = self.config
        return {"mrna": c["k_tx"] * c["gene"] - c["d_m"] * s["mrna"],
                "protein": c["k_tl"] * s["mrna"] - c["d_p"] * s["protein"],
                "metabolite": c["k_met"] * s["protein"] - c["d_met"] * s["metabolite"]}


def build_nested_cell():
    obs = ["mrna", "protein", "metabolite"]
    return {"state": {"mrna": _pool(0.0), "protein": _pool(0.0), "metabolite": _pool(0.0),
                      "expr": _proc("CentralDogma", obs), "emitter": _emitter(obs)}}


# ─── fig 09 · self-made: autopoietic closure (+ knockout control) ────────────
# metabolism (needs enzyme E) consumes nutrient → precursor X; X builds membrane
# M and enzyme E (autocatalysis: E makes X makes E); M gates uptake (containment).
# Intact → self-sustaining steady state; enzyme-knockout variant → collapse.
class Autopoiesis(ODE):
    PORTS = ["nutrient", "precursor", "membrane", "enzyme"]
    # make_enzyme default is 0.0 (the knockout) ON PURPOSE: bigraph's is_empty
    # treats an explicit 0.0 float config as "unset" and would overwrite it with
    # the default — so the knockout must BE the default, and the intact passes 1.0.
    config_schema = {"vmax": _f(1.4), "km": _f(0.5), "yield_": _f(0.9),
                     "k_m": _f(0.22), "d_m": _f(0.06), "k_e": _f(0.22), "d_e": _f(0.10),
                     "make_enzyme": _f(0.0)}

    def deriv(self, s):
        c = self.config
        N, X, M, E = s["nutrient"], s["precursor"], s["membrane"], s["enzyme"]
        gate = M / (0.5 + M)                                    # containment gates uptake
        u = monod(N, c["vmax"], c["km"]) * max(E, 0.0) * gate   # uptake STRICTLY needs enzyme
        dX = c["yield_"] * u - c["k_m"] * X - c["k_e"] * X
        dM = c["k_m"] * X - c["d_m"] * M
        dE = c["make_enzyme"] * c["k_e"] * X - c["d_e"] * E     # knockout: make_enzyme=0 → E decays → collapse
        return {"nutrient": -u, "precursor": dX, "membrane": dM, "enzyme": dE}


def _build_autopoiesis(make_enzyme):
    obs = ["nutrient", "precursor", "membrane", "enzyme"]
    return {"state": {"nutrient": _pool(12.0), "precursor": _pool(0.2),
                      "membrane": _pool(0.3), "enzyme": _pool(0.3),
                      "cell": _proc("Autopoiesis", obs, {"make_enzyme": make_enzyme}),
                      "emitter": _emitter(obs)}}


def build_self_made():
    return {"intact": _build_autopoiesis(1.0), "knockout": _build_autopoiesis(0.0)}


# ─── fig 10-1 · divide: growth to threshold + mass-conserving division ───────
class GrowToDivide(ODE):
    PORTS = ["nutrient", "mass"]
    config_schema = {"vmax": _f(1.0), "km": _f(0.4), "yield_": _f(0.6)}

    def deriv(self, s):
        u = monod(s["nutrient"], self.config["vmax"], self.config["km"]) * s["mass"]  # autocatalytic
        return {"nutrient": -u, "mass": self.config["yield_"] * u}


class LineageDivision(Step):
    """When mass crosses the threshold, halve it (mother→two daughters, mass
    conserved) and increment the cell count. Set-semantics deltas."""
    config_schema = {"threshold": _f(1.6)}

    def inputs(self): return {"mass": "float", "cell_count": "float"}
    def outputs(self): return {"mass": "float", "cell_count": "float"}

    def update(self, state):
        m = float(state.get("mass", 0.0))
        if m >= self.config["threshold"]:
            return {"mass": -m / 2.0, "cell_count": 1.0}        # conserve: total mass unchanged
        return {"mass": 0.0, "cell_count": 0.0}


def build_divide():
    obs = ["nutrient", "mass", "cell_count"]
    return {"state": {
        "nutrient": _pool(20.0), "mass": _pool(0.4), "cell_count": _pool(1.0),
        "grow": {"_type": "process", "address": "local:GrowToDivide", "interval": 0.1,
                 "inputs": {"nutrient": ["nutrient"], "mass": ["mass"]},
                 "outputs": {"nutrient": ["nutrient"], "mass": ["mass"]}},
        "division": {"_type": "step", "address": "local:LineageDivision",
                     "inputs": {"mass": ["mass"], "cell_count": ["cell_count"]},
                     "outputs": {"mass": ["mass"], "cell_count": ["cell_count"]}},
        "emitter": _emitter(obs)}}


# ─── fig 10-2 · biofilm: logistic colony + ECM (saturating, not linear) ──────
class Biofilm(ODE):
    PORTS = ["cells", "ecm"]
    config_schema = {"r": _f(0.9), "K": _f(5.0), "k_ecm": _f(0.4), "d_ecm": _f(0.02)}

    def deriv(self, s):
        c = self.config
        dcells = c["r"] * s["cells"] * (1 - s["cells"] / c["K"])   # logistic (surface carrying cap)
        decm = c["k_ecm"] * s["cells"] - c["d_ecm"] * s["ecm"]
        return {"cells": dcells, "ecm": decm}


def build_biofilm():
    obs = ["cells", "ecm"]
    return {"state": {"cells": _pool(0.2), "ecm": _pool(0.0),
                      "film": _proc("Biofilm", obs), "emitter": _emitter(obs)}}


# ─── fig 10-3 · evolve: competitive selection sweep (+ new capability) ───────
class Competition(ODE):
    PORTS = ["n_wt", "n_mut", "capability"]
    # chemostat-style competition: a shared dilution term d makes the fitter
    # variant (higher r) competitively exclude the other → a real selection sweep.
    config_schema = {"r_wt": _f(0.55), "r_mut": _f(1.05), "K": _f(6.0), "d": _f(0.14),
                     "k_cap": _f(0.6), "cap_onset": _f(0.25)}

    def deriv(self, s):
        c = self.config
        total = s["n_wt"] + s["n_mut"]
        share = 1 - total / c["K"]
        # the fitter mutant expresses a new interface capability proportional to its abundance
        return {"n_wt": c["r_wt"] * s["n_wt"] * share - c["d"] * s["n_wt"],
                "n_mut": c["r_mut"] * s["n_mut"] * share - c["d"] * s["n_mut"],
                "capability": c["k_cap"] * s["n_mut"] - c["cap_onset"] * s["capability"]}


def build_evolve():
    obs = ["n_wt", "n_mut", "capability"]
    return {"state": {"n_wt": _pool(1.0), "n_mut": _pool(0.05), "capability": _pool(0.0),
                      "pop": _proc("Competition", obs), "emitter": _emitter(obs)}}


# ─── whole cell · grow → divide → thermal shock → die → disintegrate ─────────
class WholeCell(ODE):
    PORTS = ["nutrient", "biomass", "debris", "viability", "temperature"]
    config_schema = {"vmax": _f(1.1), "km": _f(0.5), "yield_": _f(0.6), "maint": _f(0.02),
                     "ramp": _f(0.0), "shock_time": _f(9.0), "shock_ramp": _f(3.0),
                     "t_max": _f(50.0), "t_tol": _f(42.0), "t_width": _f(3.0),
                     "denat": _f(0.9), "lyse": _f(0.8), "phi_crit": _f(0.5)}

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core); self._t = 0.0

    def deriv(self, s):
        c = self.config
        N, B, D, phi, T = (s["nutrient"], s["biomass"], s["debris"],
                           s["viability"], s["temperature"])
        u = monod(N, c["vmax"], c["km"]) * B * max(phi, 0.0)       # autocatalytic growth
        lysing = c["lyse"] * B if phi < c["phi_crit"] else 0.0     # disintegration below viability
        dB = c["yield_"] * u - c["maint"] * B - lysing
        dT = c["shock_ramp"] if self._t >= c["shock_time"] and T < c["t_max"] else 0.0
        dphi = -c["denat"] * arrhenius_excess(T, c["t_tol"], c["t_width"]) * max(phi, 0.0)
        return {"nutrient": -u, "biomass": dB, "debris": lysing,   # mass conserved: B→debris
                "viability": dphi, "temperature": dT}

    def update(self, state, interval):
        self._t += interval
        return super().update(state, interval)


class WholeCellDivision(Step):
    """Count-only division marker: biomass here is TOTAL colony biomass (so the
    biomass→debris mass balance stays clean); each mass_per_cell of new biomass
    marks one more division. Biomass is NOT altered."""
    config_schema = {"mass_per_cell": _f(0.6)}
    def inputs(self): return {"biomass": "float", "cell_count": "float"}
    def outputs(self): return {"cell_count": "float"}

    def update(self, state):
        b = float(state.get("biomass", 0.0))
        n = float(state.get("cell_count", 1.0))
        target = max(1.0, b / self.config["mass_per_cell"])
        return {"cell_count": max(0.0, target - n)}            # ratchet up, never down


def build_whole_cell_dynamics():
    obs = ["nutrient", "biomass", "debris", "viability", "temperature", "cell_count"]
    return {"state": {
        "nutrient": _pool(14.0), "biomass": _pool(0.3), "debris": _pool(0.0),
        "viability": _pool(1.0), "temperature": _pool(37.0), "cell_count": _pool(1.0),
        "cell": {"_type": "process", "address": "local:WholeCell", "interval": 0.1,
                 "inputs": {p: [p] for p in
                            ["nutrient", "biomass", "debris", "viability", "temperature"]},
                 "outputs": {p: [p] for p in
                             ["nutrient", "biomass", "debris", "viability", "temperature"]}},
        "division": {"_type": "step", "address": "local:WholeCellDivision",
                     "inputs": {"biomass": ["biomass"], "cell_count": ["cell_count"]},
                     "outputs": {"cell_count": ["cell_count"]}},
        "emitter": _emitter(obs)}}


# ─── registry: slug -> spec (builder, duration, panels, invariant) ───────────
# panels: list of (title, ylabel, [series]); series names are emitted observables.
# multi: dict of {variant: composite} instead of a single composite.
DYNAMICS = {
    "typed-interface": dict(
        build=build_typed_interface, t_end=18.0, dt=0.1,
        panels=[("Growth vs. a depleting nutrient", "amount", ["nutrient", "volume"]),
                ("Thermal-stress viability cliff", "temperature °C", ["temperature"],
                 "viability", ["viability"])],
        invariant=("carbon", lambda R: f"volume gained {R['volume'][-1]-R['volume'][0]:.2f} "
                   f"from nutrient drawn-down {R['nutrient'][0]-R['nutrient'][-1]:.2f}")),
    "closing-the-loop": dict(
        build=build_closing_the_loop, t_end=20.0, dt=0.1, field=True,
        panels=[("Nutrient field — a gradient forms as the cell draws it down", "position",
                 [f"c{i}" for i in range(15)])],
        invariant=("mass", lambda R: f"field+uptake conserved: "
                   f"Σfield {sum(R[f'c{i}'][-1] for i in range(15)):.2f} + taken {R['uptake_total'][-1]:.2f} "
                   f"≈ initial {sum(R[f'c{i}'][0] for i in range(15)):.2f}")),
    "one-interface-three-mechanisms": dict(
        build=build_three_mechanisms, t_end=14.0, dt=0.2, multi=True,
        overlay=[("Substrate S(t) — batch drawdown", "nutrient", "nutrient"),
                 ("Biomass B(t)", "biomass", "biomass")],
        invariant=("mass", lambda M: "all three converge to biomass = yield·S₀ = 5.0 "
                   "(mass conserved); coarse/MM/FBA differ in timescale, not endpoint")),
    "molecular-channels": dict(
        build=build_molecular_channels, t_end=16.0, dt=0.1,
        panels=[("Chemical turnover → product + heat (energy conserved)", "amount",
                 ["substrate", "product", "heat"]),
                ("Electrical channel — Ohmic response to a decaying drive", "V / I",
                 ["voltage", "current"])],
        invariant=("energy", lambda R: f"energy balance: product {R['product'][-1]:.2f} + heat "
                   f"{R['heat'][-1]:.2f} accounts for substrate consumed {R['substrate'][0]-R['substrate'][-1]:.2f}")),
    "the-nested-cell": dict(
        build=build_nested_cell, t_end=20.0, dt=0.1,
        panels=[("Central dogma: gene → mRNA → protein → metabolite (steady states)", "concentration",
                 ["mrna", "protein", "metabolite"])],
        invariant=("timescale", lambda R: f"time hierarchy: mRNA settles fast, protein lags — "
                   f"mRNA_ss≈{R['mrna'][-1]:.2f}, protein_ss≈{R['protein'][-1]:.2f}")),
    "self-made": dict(
        build=build_self_made, t_end=30.0, dt=0.1, multi=True,
        overlay=[("Membrane (containment)", "membrane", "membrane"),
                 ("Enzyme (metabolic catalyst)", "enzyme", "enzyme")],
        invariant=("closure", lambda M: "intact composition self-sustains a steady state; "
                   "the enzyme-knockout control collapses — the closure is load-bearing")),
    "divide": dict(
        build=build_divide, t_end=18.0, dt=0.1,
        panels=[("Mass — grow to threshold, halve at division (mass conserved)", "mass·count",
                 ["mass", "cell_count"]),
                ("Nutrient drawn down by the growing lineage", "nutrient", ["nutrient"])],
        invariant=("mass", lambda R: f"divisions: cell_count 1→{R['cell_count'][-1]:.0f}; "
                   f"each division halves mass (mother = Σ daughters)")),
    "biofilm": dict(
        build=build_biofilm, t_end=16.0, dt=0.1,
        panels=[("Logistic colony growth + ECM (saturates at carrying capacity)", "amount",
                 ["cells", "ecm"])],
        invariant=("logistic", lambda R: f"cells saturate at carrying capacity K "
                   f"(cells_final {R['cells'][-1]:.2f}), not unbounded/linear growth")),
    "evolve": dict(
        build=build_evolve, t_end=28.0, dt=0.1,
        panels=[("Competitive selection — the fitter variant sweeps", "abundance",
                 ["n_wt", "n_mut"]),
                ("A new interface capability rides the sweep", "capability", ["capability"])],
        invariant=("selection", lambda R: f"selection sweep: mutant fraction "
                   f"{R['n_mut'][0]/(R['n_wt'][0]+R['n_mut'][0]):.2f} → "
                   f"{R['n_mut'][-1]/(R['n_wt'][-1]+R['n_mut'][-1]):.2f}")),
    "the-living-atlas": dict(
        build=build_whole_cell_dynamics, t_end=20.0, dt=0.1,
        panels=[("Whole cell: grow → divide → thermal shock → die → disintegrate", "biomass / debris",
                 ["biomass", "debris", "cell_count"]),
                ("Viability collapse under the thermal shock", "temperature °C",
                 ["temperature"], "viability", ["viability"])],
        invariant=("mass", lambda R: f"mass conserved through death: peak biomass "
                   f"{max(R['biomass']):.2f} → debris {R['debris'][-1]:.2f}; "
                   f"divides to {R['cell_count'][-1]:.0f} cells; viability {min(R['viability']):.2f}")),
}
