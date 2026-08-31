"""Fig 2 · orchestration across timescales — a MINIMAL executable demonstration.

Fig 2 is the orchestration overview. Its panel (a) — *multi-timestepping* —
is the piece with genuine, non-forced dynamics: several processes update at
**different rates** through a **shared store**, and the engine interleaves their
steps on one clock. (Panels (b) workflow-DAG and (c) event-driven graph rewrites
are structural/schematic; this module deliberately demonstrates only (a), the
part a minimal run can show honestly.)

Two processes share one pool store:

* :class:`FastProduction` (``interval = 1.0``) — a fast process that adds to the
  shared ``molecules`` pool every base tick: ``dmolecules/dt = +rate``.
* :class:`SlowConversion` (``interval = 5.0``) — a slow process that fires once
  per 5 ticks, converting a fraction of whatever has accumulated into ``biomass``
  and drawing that amount back out of the pool.

Run together they show the multiscale signature: ``molecules`` ramps up on the
fast clock and drops in a sawtooth each time the slow process fires, while
``biomass`` advances in coarse staircase steps on the slow clock — two rates
coordinated through the one shared store. That is exactly the multi-timestepping
claim of Fig 2a, made runnable.

Both auto-registered at ``local:<ClassName>`` by ``build_core`` (top-level module).
"""
from __future__ import annotations

from process_bigraph import Process


class FastProduction(Process):
    """Fast process: adds to the shared ``molecules`` pool every base tick
    (``dmolecules/dt = +rate``). Runs on the short interval."""

    config_schema = {"rate": {"_type": "float", "_default": 1.0}}

    def inputs(self):
        return {"molecules": "float"}

    def outputs(self):
        return {"molecules": "float"}

    def update(self, state, interval):
        return {"molecules": self.config["rate"] * interval}


class SlowConversion(Process):
    """Slow process: fires on the long interval and converts a fraction of the
    accumulated pool into ``biomass``, drawing that amount back out of the pool.

    Writes ``+converted`` to ``biomass`` and ``-converted`` to ``molecules`` where
    ``converted = yield_frac * molecules`` — a coarse, infrequent step against the
    fast pool fill, so the two processes visibly run at different rates through the
    one shared store.
    """

    config_schema = {"yield_frac": {"_type": "float", "_default": 0.6}}

    def inputs(self):
        return {"molecules": "float"}

    def outputs(self):
        return {"molecules": "float", "biomass": "float"}

    def update(self, state, interval):
        converted = self.config["yield_frac"] * float(state["molecules"])
        return {"biomass": +converted, "molecules": -converted}
