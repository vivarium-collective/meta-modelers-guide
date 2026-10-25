"""Fig 2 · orchestration across timescales — a *mechanistic* multirate model.

Real-mechanism upgrade of ``fig02_demo`` (FastProduction/SlowConversion, kept as
the didactic baseline). The baseline's "molecules + biomass == time" equality is a
CUMULATIVE EXTERNAL-INPUT budget (influx = 1/tick, no losses), not closed-system
mass conservation — this variant makes that explicit and separates two things the
baseline conflated:

  * MULTIRATE SCHEDULING — which clock fires when (a fast metabolite process and a
    slow biomass process share one pool on different intervals), and
  * NUMERICAL ACCURACY — how close the coarse-scheduled run is to a fine-step
    reference (an explicit-Euler convergence question, O(Δt)).

Model (two processes, one shared ``metabolite`` pool):

  FastMetabolism (short interval): influx I into the pool, minus a STIFF first-order
    turnover r·M routed to a ``waste`` sink. M relaxes fast to the quasi-steady
    M* = I/r, so the fast process genuinely needs a small timestep to be accurate.
  SlowBiomass (long interval): converts k_b·M of the pool per slow step, a yield
    fraction y to ``biomass`` and the remainder (1−y) to ``waste``.

Explicit input–output ledger (the honest replacement for "pool+biomass==time"):
    cumulative_input  =  ΔM + Δbiomass + Δwaste    (exactly, every step)
so biomass is only the y-fraction of what is converted; M + B is NOT conserved
because waste (turnover + conversion loss) also carries mass. Both processes read
the pool at the tick boundary and return DELTAS that the engine sums, so coincident
fast/slow updates are SYNCHRONOUS and the result is independent of their order.

All classes auto-register at ``local:<ClassName>`` via build_core.
"""
from __future__ import annotations

from process_bigraph import Process


def _f(default):
    return {"_type": "float", "_default": default}


class FastMetabolism(Process):
    """Fast, stiff metabolite turnover on the short clock: dM = (I − r·M)·dt, with
    the influx I tracked as cumulative input and the turnover r·M routed to waste.
    Relaxes to the quasi-steady M* = I/r; needs a small dt for accuracy (explicit
    Euler is stable for r·dt < 2, accurate for r·dt ≪ 1)."""

    config_schema = {"influx": _f(1.0), "turnover": _f(1.5)}

    def inputs(self):
        return {"metabolite": "float"}

    def outputs(self):
        return {"metabolite": "float", "waste": "float", "cumulative_input": "float"}

    def update(self, state, interval):
        m = float(state.get("metabolite", 0.0))
        i_in = self.config["influx"] * interval
        turned = self.config["turnover"] * m * interval
        return {
            "metabolite": i_in - turned,
            "waste": turned,
            "cumulative_input": i_in,
        }


class SlowBiomass(Process):
    """Slow biomass conversion on the long clock: removes k_b·M·dt from the pool,
    routes a yield fraction y to biomass and (1−y) to waste. Reads the same pool as
    FastMetabolism; returns deltas the engine sums (synchronous at coincident ticks)."""

    config_schema = {"k_bio": _f(0.3), "yield_frac": _f(0.6)}

    def inputs(self):
        return {"metabolite": "float"}

    def outputs(self):
        return {"metabolite": "float", "biomass": "float", "waste": "float"}

    def update(self, state, interval):
        m = float(state.get("metabolite", 0.0))
        removed = self.config["k_bio"] * m * interval
        y = self.config["yield_frac"]
        return {
            "metabolite": -removed,
            "biomass": y * removed,
            "waste": (1.0 - y) * removed,
        }
