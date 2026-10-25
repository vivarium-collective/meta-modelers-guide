"""Fig 8 · self-organized processes — a *mechanistic* self-maintaining cell with
a real boundary, turnover, repair, energy/material constraints and viability.

This is the real-mechanism upgrade of ``handlers_fig08b`` (the flat-pool coupled
ODEs kept as the didactic baseline). The baseline shows DEPENDENCE via process
knockout but its pools only accumulate — there is no membrane that gates anything,
no turnover, no repair, no failure, so it cannot show the properties that make
"self-maintenance" meaningful: persistence at a steady state, replacement of
components as they degrade, and recovery after damage.

OPERATIONAL CLOSURE (defined before we use the word, per the review)
-------------------------------------------------------------------
The cell is operationally closed iff the components it needs to persist are
produced by processes that themselves depend on those components:

    membrane ──gates──▶ nutrient import ──feeds──▶ metabolism (needs enzymes)
        ▲                                               │
        │                                     produces ATP + precursors
        └──────── repair (needs precursor+ATP) ◀────────┤
                                                         ▼
                              enzyme synthesis (needs precursor+ATP) ──▶ enzymes

BOUNDARY MAINTENANCE = the membrane area is held against first-order degradation
by repair flux; it is a scalar ``area`` state, not a spatial bilayer. Everything
degrades (turnover), so persistence REQUIRES continuous replacement — the cell is
a far-from-equilibrium steady state, not an accumulating pile.

What is a DERIVED (non-scripted) outcome here: the steady-state levels of every
pool, the fact that a transient membrane injury is REPAIRED back to that steady
state, and that breaking any one edge of the loop drives viability to zero. What
is NOT emergent and is honestly scripted: the viability target function, the rate
constants, and the membrane being a scalar (no spatial self-production). So this
demonstrates operational closure, homeostasis and recovery — DEPENDENCE and
self-maintenance in the organizational sense — but NOT autopoiesis in the strong
sense of a boundary the system produces for itself in space.

Classes auto-register at ``local:<ClassName>`` via build_core. Knockouts and
"open-loop" use an EPSILON rate, never 0.0 (a float 0.0 config is restored to the
schema default by bigraph_schema).
"""
from __future__ import annotations

from process_bigraph import Process


def _f(default):
    return {"_type": "float", "_default": default}


class NutrientReservoir(Process):
    """The external medium. In CLOSED-LOOP (replenish≈0) the cell draws down a
    finite reservoir; in OPEN-LOOP (replenish large) the medium is held up by an
    external supply — the matched external-input control the review asks for."""
    config_schema = {"replenish": _f(0.6), "cap": _f(5.0)}

    def inputs(self):
        return {"nutrient_ext": "concentration"}

    def outputs(self):
        return {"nutrient_ext": "concentration", "supplied_total": "concentration"}

    def update(self, state, interval):
        ext = float(state.get("nutrient_ext", 0.0))
        add = self.config["replenish"] * interval
        if ext + add > self.config["cap"]:        # don't overfill the medium
            add = max(self.config["cap"] - ext, 0.0)
        return {"nutrient_ext": add, "supplied_total": add}


class SelfMaintainingCell(Process):
    """The whole cell as one coupled ODE over its shared stores. Membrane gates
    nutrient import; metabolism (enzyme-catalysed) turns internal nutrient into ATP
    and precursors; precursor+ATP are spent to SYNTHESISE enzymes and REPAIR the
    membrane; every component DEGRADES (turnover); viability relaxes toward the
    cell's health (membrane adequacy × energy charge). A one-time membrane injury at
    ``perturb_at`` lets the cell show recovery. Mechanism knockouts: set
    ``k_transport`` / ``k_met`` / ``k_expr`` / ``k_repair`` to epsilon (NOT 0.0)."""

    config_schema = {
        # transport & metabolism
        "k_transport": _f(0.5),     # import = k_transport·membrane·nutrient_ext
        "k_met": _f(0.8),           # metabolism flux = k_met·enzymes·nutrient_int/(Km+nutrient_int)
        "km_nut": _f(0.4),
        "y_energy": _f(1.0),        # ATP produced per unit metabolic flux
        "y_precursor": _f(0.8),     # precursor produced per unit metabolic flux
        # synthesis (ATP-costed), repair, degradation
        "k_expr": _f(0.6),          # enzyme synthesis = k_expr·precursor·energy_charge
        "k_repair": _f(0.6),        # membrane repair  = k_repair·precursor·energy_charge
        "km_energy": _f(0.3),       # ATP saturation for synthesis (energy charge)
        "atp_cost": _f(0.5),        # ATP spent per unit (enzyme+membrane) synthesised
        "deg_enzyme": _f(0.08),     # first-order turnover
        "deg_membrane": _f(0.06),
        "deg_energy": _f(0.10),     # maintenance ATP drain
        "deg_precursor": _f(0.04),
        # viability & perturbation
        "membrane_ref": _f(2.5),    # membrane area at which the boundary is "healthy"
        "viab_relax": _f(0.3),
        "perturb_at": _f(-1.0),     # tick to injure the membrane (<0 = never)
        "perturb_frac": _f(0.6),    # fraction of membrane removed by the injury
    }

    def inputs(self):
        return {
            "nutrient_ext": "concentration", "nutrient_int": "concentration",
            "energy": "energy", "precursor": "concentration",
            "enzymes": "concentration", "membrane": "area", "viability": "viability",
        }

    def outputs(self):
        return {
            "nutrient_ext": "concentration", "nutrient_int": "concentration",
            "energy": "energy", "precursor": "concentration",
            "enzymes": "concentration", "membrane": "area", "viability": "viability",
            # instantaneous readouts (set-semantics)
            "import_flux": "chemical_flux", "metabolic_flux": "chemical_flux",
            "repair_flux": "chemical_flux", "energy_charge": "float",
            # cumulative accounting (accumulate)
            "imported_total": "concentration",
        }

    def _set(self, port, value):
        if not hasattr(self, "_last"):
            self._last = {}
        d = value - self._last.get(port, 0.0)
        self._last[port] = value
        return d

    def update(self, state, interval):
        c = self.config
        if not hasattr(self, "_t"):
            self._t = 0.0

        ext = max(float(state.get("nutrient_ext", 0.0)), 0.0)
        nint = max(float(state.get("nutrient_int", 0.0)), 0.0)
        energy = max(float(state.get("energy", 0.0)), 0.0)
        prec = max(float(state.get("precursor", 0.0)), 0.0)
        enz = max(float(state.get("enzymes", 0.0)), 0.0)
        mem = max(float(state.get("membrane", 0.0)), 0.0)
        viab = float(state.get("viability", 0.0))

        energy_charge = energy / (c["km_energy"] + energy)   # 0..1 ATP availability

        # 1. membrane-gated import (needs the boundary)
        import_flux = c["k_transport"] * mem * ext
        import_flux = min(import_flux, ext / max(interval, 1e-9))   # can't import more than present

        # 2. enzyme-catalysed metabolism → ATP + precursors (needs enzymes + nutrient)
        metabolic_flux = c["k_met"] * enz * nint / (c["km_nut"] + nint)
        metabolic_flux = min(metabolic_flux, nint / max(interval, 1e-9))

        # 3. synthesis of enzymes and membrane repair (need precursor + ATP)
        expr_flux = c["k_expr"] * prec * energy_charge
        repair_flux = c["k_repair"] * prec * energy_charge
        synth_total = expr_flux + repair_flux
        # cap precursor draw to what's available
        if synth_total * interval > prec:
            scale = prec / max(synth_total * interval, 1e-12)
            expr_flux *= scale; repair_flux *= scale; synth_total *= scale
        atp_spent = c["atp_cost"] * synth_total
        if atp_spent * interval > energy:            # cap ATP spend to what's available
            scale = energy / max(atp_spent * interval, 1e-12)
            expr_flux *= scale; repair_flux *= scale; synth_total *= scale; atp_spent *= scale

        # 4. first-order turnover (everything degrades → replacement required)
        d_enz = (expr_flux - c["deg_enzyme"] * enz) * interval
        d_mem = (repair_flux - c["deg_membrane"] * mem) * interval
        d_prec = (c["y_precursor"] * metabolic_flux - synth_total - c["deg_precursor"] * prec) * interval
        d_energy = (c["y_energy"] * metabolic_flux - atp_spent - c["deg_energy"] * energy) * interval
        d_nint = (import_flux - metabolic_flux) * interval
        d_ext = -import_flux * interval

        # 5. one-time membrane injury (to demonstrate repair/recovery)
        self._t += interval
        if c["perturb_at"] >= 0 and (self._t - interval) < c["perturb_at"] <= self._t:
            d_mem -= c["perturb_frac"] * mem

        # 6. viability relaxes toward health = boundary adequacy × energy charge
        health = min(mem / c["membrane_ref"], 1.0) * energy_charge
        health = max(0.0, min(health, 1.0))
        d_viab = c["viab_relax"] * (health - viab) * interval

        return {
            "nutrient_ext": d_ext, "nutrient_int": d_nint, "energy": d_energy,
            "precursor": d_prec, "enzymes": d_enz, "membrane": d_mem, "viability": d_viab,
            "import_flux": self._set("import_flux", import_flux),
            "metabolic_flux": self._set("metabolic_flux", metabolic_flux),
            "repair_flux": self._set("repair_flux", repair_flux),
            "energy_charge": self._set("energy_charge", energy_charge),
            "imported_total": import_flux * interval,
        }
