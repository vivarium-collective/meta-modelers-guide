"""Fig 5 · disintegration / grain-switch — a *mechanistic* multiscale cell that
refines its own grain when a quantified model-inadequacy signal crosses tolerance.

This is the real-mechanism upgrade of ``fig05_grain`` (the baseline, which flips
grain on a bare viability threshold and presents the switch as if biological
disintegration *required* the fine grain). Here two things are deliberately kept
SEPARATE, as the review asks:

1. The **biological damage state** evolves continuously and is grain-independent:
   misfolded protein is produced by stress, repaired using energy, and — the part
   that matters at the boundary — AGGREGATES autocatalytically (``k_agg·m_sol²``)
   into an irreversible aggregate pool once it accumulates. Aggregates are far more
   damaging to viability than soluble misfolded protein, so viability shows a CLIFF
   the linear coarse model cannot see.

2. The **grain selection** is an algorithmic choice driven by a *computable*
   inadequacy estimator — the fraction of the local damage dynamics carried by the
   neglected aggregation term, ``k_agg·m²/(linear-rate + k_agg·m²)``. While that
   fraction is small the cheap COARSE grain (linear, aggregation neglected) is
   adequate; once it exceeds ``inadequacy_tol`` the FINE grain (resolving
   soluble vs aggregated protein) is swapped in. This is a quantified error
   indicator, NOT a wall-clock t=13.

Coarse↔fine maps conserve the mapped state at handover: PROLONGATION (coarse→fine)
puts all coarse damage into the soluble pool (``m_sol = m``, ``m_agg = 0``), so the
restriction (``m = m_sol + m_agg``) matches exactly and neither total damage nor
biomass jumps at the switch (``handover_error = 0``). Biomass is paid continuously.

``mode`` selects the control arm: ``adaptive`` (default — refine on the inadequacy
signal), ``coarse`` (always-coarse: aggregation never resolved), ``fine``
(always-fine: aggregation resolved from t=0). Comparing the three isolates what the
refinement buys. All classes auto-register at ``local:<ClassName>`` via build_core.
"""
from __future__ import annotations

from process_bigraph import Process

_EPS = 1e-12


def _f(default):
    return {"_type": "float", "_default": default}


class StressRamp5(Process):
    """External stressor: ramps the stress level the cell experiences from
    ``stress0`` by ``stress_rate`` per unit time (set-semantics into the shared
    stress store)."""
    config_schema = {"stress0": _f(0.15), "stress_rate": _f(0.03), "stress_max": _f(1.0)}

    def inputs(self):
        return {}

    def outputs(self):
        return {"stress": "concentration"}

    def update(self, state, interval):
        if not hasattr(self, "_t"):
            self._t = 0.0
            self._last = 0.0
        self._t += interval
        value = min(self.config["stress0"] + self.config["stress_rate"] * self._t,
                    self.config["stress_max"])
        delta = value - self._last
        self._last = value
        return {"stress": delta}


class GrainAdaptiveCell(Process):
    """A multiscale cell whose damage state (soluble + aggregated misfolded protein)
    and biomass evolve continuously, and whose active grain is chosen by a computable
    inadequacy estimator. ``mode`` ∈ {adaptive, coarse, fine}.

    State written to shared stores so the emitter captures the biology (m_sol, m_agg,
    total damage, viability, biomass) SEPARATELY from the algorithmic state
    (active_grain, inadequacy, handover_error)."""

    config_schema = {
        "mode": {"_type": "string", "_default": "adaptive"},
        "k_stress": _f(0.045),       # misfolded protein produced per unit stress
        "k_repair": _f(0.030),       # repair rate (× energy)
        "energy": _f(1.0),           # (constant) energy available for repair
        "k_agg": _f(0.55),           # autocatalytic aggregation rate (the neglected nonlinearity)
        "w_sol": _f(0.35),           # viability damage weight of soluble misfolded protein
        "w_agg": _f(1.7),            # viability damage weight of aggregates (far more toxic)
        "mu": _f(0.12),              # biomass growth rate (× viability)
        "inadequacy_tol": _f(0.20),  # refine when the neglected-term fraction exceeds this
    }

    def inputs(self):
        return {"stress": "concentration", "m_sol": "concentration",
                "m_agg": "concentration", "biomass": "mass"}

    def outputs(self):
        return {"m_sol": "concentration", "m_agg": "concentration", "biomass": "mass",
                "damage": "concentration", "viability": "viability",
                "active_grain": "fraction", "inadequacy": "fraction",
                "handover_error": "concentration"}

    def _set(self, port, value):
        if not hasattr(self, "_last_set"):
            self._last_set = {}
        d = value - self._last_set.get(port, 0.0)
        self._last_set[port] = value
        return d

    def update(self, state, interval):
        c = self.config
        mode = c["mode"]
        stress = float(state.get("stress", 0.0))
        m_sol = max(float(state.get("m_sol", 0.0)), 0.0)
        m_agg = max(float(state.get("m_agg", 0.0)), 0.0)
        biomass = float(state.get("biomass", 1.0))
        energy = c["energy"]

        # computable inadequacy: fraction of local damage dynamics carried by the
        # neglected autocatalytic aggregation term (estimated from the coarse state).
        linear_rate = c["k_stress"] * stress + c["k_repair"] * energy * m_sol
        agg_flux = c["k_agg"] * m_sol * m_sol
        inadequacy = agg_flux / (linear_rate + agg_flux + _EPS)

        # grain selection
        if not hasattr(self, "_refined"):
            self._refined = False
            self._switch_recorded = False
        if mode == "coarse":
            grain_fine = False
        elif mode == "fine":
            grain_fine = True
        else:  # adaptive
            if not self._refined and inadequacy > c["inadequacy_tol"]:
                self._refined = True
            grain_fine = self._refined

        # handover conservation: PROLONGATION is identity on the shared damage pools
        # (coarse already keeps m_agg=0, m_sol=m), so total damage and biomass are
        # continuous at the switch → residual 0. Record it at the switch tick.
        handover_error = 0.0
        if grain_fine and not self._switch_recorded and mode == "adaptive":
            self._switch_recorded = True
            # coarse_total (before map) = m_sol; fine_total (after prolong) = m_sol + m_agg
            handover_error = abs((m_sol + m_agg) - m_sol)   # == 0 by construction

        # damage dynamics — soluble production/repair always; aggregation ONLY when
        # the fine grain is active (coarse neglects it → the two grains diverge).
        d_sol = (c["k_stress"] * stress - c["k_repair"] * energy * m_sol) * interval
        if grain_fine:
            agg = agg_flux * interval
            # aggregation moves mass soluble → aggregated (conserved transfer)
            d_sol -= agg
            d_agg = agg
        else:
            d_agg = 0.0

        m_sol_new = max(m_sol + d_sol, 0.0)
        m_agg_new = max(m_agg + d_agg, 0.0)
        total_damage = m_sol_new + m_agg_new
        viability = max(0.0, 1.0 - c["w_sol"] * m_sol_new - c["w_agg"] * m_agg_new)

        # biomass grows with viability (no artificial jump at the switch — biomass is
        # never reset by the grain map, only grown/declined by the active dynamics).
        d_biomass = c["mu"] * viability * interval

        return {
            "m_sol": m_sol_new - m_sol,
            "m_agg": m_agg_new - m_agg,
            "biomass": d_biomass,
            "damage": self._set("damage", total_damage),
            "viability": self._set("viability", viability),
            "active_grain": self._set("active_grain", 1.0 if grain_fine else 0.0),
            "inadequacy": self._set("inadequacy", inadequacy),
            "handover_error": self._set("handover_error", handover_error),
        }
