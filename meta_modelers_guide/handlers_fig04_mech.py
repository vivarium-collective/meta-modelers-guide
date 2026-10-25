"""Fig 4 (fig-05 in the paper) · cell–environment coupling — a *mechanistic*
reaction–diffusion field with a motile, nutrient-depleting cell.

This is the real-mechanism upgrade of ``handlers_fig04``. The baseline wires a
real 1-D diffusion field, but the cell's ``uptake`` is a scalar output that is
**never subtracted from the field** — so there is no genuine cell→field
feedback, and an "uptake ∝ local field" readout is true by construction, not
evidence of coupling (exactly the review's objection).

Here the loop is closed, on a 1-D lattice (distances in LATTICE units, dx = 1):

* ``DiffusionField`` — real finite-difference diffusion ``D·∇²c`` (Neumann edges,
  mass-conserving to round-off).
* ``FieldSource`` — IN-DOMAIN replenishment: a localized influx at ``source_index``
  plus first-order decay everywhere, so a standing nutrient gradient develops
  inside the domain (not injected from outside).
* ``MotileCell`` — a cell at a continuous lattice position that (a) takes up
  nutrient with **saturating Michaelis–Menten** kinetics ``v = Vmax·c/(Km+c)``,
  (b) **removes that uptake from the field at its location** (a real sink → a
  depletion well that diffuses), (c) grows biomass by ``yield·v``, and (d)
  **chemotaxes up the local gradient** ``dx = χ·∂c/∂x``. Turning off uptake,
  motility, or the gradient each removes exactly one arm of the loop.

Mass ledger (checkable): with Neumann edges, Σfield(t) − Σfield(0) =
Σsource − Σdecay − Σuptake, and biomass(t) − biomass(0) = yield·Σuptake. Nothing
is created; the cell's growth is paid for out of the field.

All classes auto-register at ``local:<ClassName>`` via build_core. Field stores are
``map[float]`` grids (see handlers_fig04 for why map, not array/list).
"""
from __future__ import annotations

from process_bigraph import Process


def _to_list(field) -> list[float]:
    return [float(field[str(i)]) for i in range(len(field))]


def _delta_map(deltas) -> dict:
    return {str(i): deltas[i] for i in range(len(deltas))}


def _laplacian(v: list[float]) -> list[float]:
    n = len(v)
    lap = [0.0] * n
    for i in range(n):
        left = v[i - 1] if i > 0 else v[i]
        right = v[i + 1] if i < n - 1 else v[i]
        lap[i] = left - 2.0 * v[i] + right
    return lap


def _f(default):
    return {"_type": "float", "_default": default}


class DiffusionField(Process):
    """Real finite-difference diffusion on the chemical grid: D·∇²c·interval,
    zero-flux (Neumann) edges. dx = 1 lattice unit, so D is in lattice²·tick⁻¹.
    Mass-conserving to round-off (the Neumann Laplacian sums to zero)."""
    config_schema = {"diffusivity": _f(0.4)}

    def inputs(self):
        return {"chemical_field": "map[float]"}

    def outputs(self):
        return {"chemical_field": "map[float]"}

    def update(self, state, interval):
        field = _to_list(state["chemical_field"])
        lap = _laplacian(field)
        d = self.config["diffusivity"]
        return {"chemical_field": _delta_map([d * lap[i] * interval for i in range(len(field))])}


class FieldSource(Process):
    """In-domain replenishment: a localized influx at ``source_index`` plus
    first-order decay everywhere. dfield/dt = source·δ(source_index) − k·field.
    This builds a standing gradient from inside the domain (source is explicit,
    not an unlabelled boundary condition)."""
    config_schema = {
        "source_index": {"_type": "integer", "_default": 0},
        "source_rate": _f(0.30),
        "decay_rate": _f(0.005),
    }

    def inputs(self):
        return {"chemical_field": "map[float]"}

    def outputs(self):
        # source_total / decay_total ACCUMULATE (running cumulative totals for the
        # mass ledger); the field delta is the per-tick source−decay.
        return {"chemical_field": "map[float]", "source_total": "chemical_flux", "decay_total": "chemical_flux"}

    def update(self, state, interval):
        field = _to_list(state["chemical_field"])
        c = self.config
        decay = [c["decay_rate"] * field[i] * interval for i in range(len(field))]
        deltas = [-x for x in decay]
        src = c["source_index"]
        src_in = 0.0
        if 0 <= src < len(deltas):
            src_in = c["source_rate"] * interval
            deltas[src] += src_in
        return {
            "chemical_field": _delta_map(deltas),
            "source_total": src_in,          # additive → cumulative Σ source
            "decay_total": sum(decay),       # additive → cumulative Σ decay
        }


class MotileCell(Process):
    """A cell at a continuous lattice position that closes the sense/act loop:
    saturating uptake that DEPLETES the field at its location, biomass growth paid
    out of that uptake, and chemotaxis up the local gradient. Controls are config
    switches: ``vmax=0`` (no uptake), ``chemotaxis=0`` (no motility)."""
    config_schema = {
        "vmax": _f(0.45),            # max uptake rate (field·tick⁻¹)
        "km": _f(0.30),              # Michaelis constant (field units)
        "yield_coef": _f(0.6),       # biomass per unit uptake
        "chemotaxis": _f(9.0),       # χ: lattice·tick⁻¹ per unit gradient
        "max_step": _f(1.0),         # clamp |Δposition| per tick (lattice units)
    }

    def inputs(self):
        return {"chemical_field": "map[float]", "position": "length", "biomass": "mass"}

    def outputs(self):
        return {
            "chemical_field": "map[float]",   # the depletion sink (−uptake at the cell)
            "position": "length",             # chemotactic displacement (accumulates)
            "biomass": "mass",                # growth (accumulates)
            "uptake": "chemical_flux",        # instantaneous uptake (set)
            "uptake_total": "chemical_flux",  # cumulative Σ uptake (accumulates) — for the ledger
            "local_conc": "concentration",    # field at the cell (set)
            "gradient": "concentration",      # ∂c/∂x at the cell (set)
        }

    def _set(self, port, value):
        if not hasattr(self, "_last"):
            self._last = {}
        d = value - self._last.get(port, 0.0)
        self._last[port] = value
        return d

    def update(self, state, interval):
        field = _to_list(state["chemical_field"])
        n = len(field)
        c = self.config
        x = float(state.get("position", n / 2))
        idx = int(round(x))
        idx = max(0, min(idx, n - 1))
        local = field[idx]

        # saturating (Michaelis–Menten) uptake, removed from the field at the cell
        v = c["vmax"] * local / (c["km"] + local) if local > 0 else 0.0
        uptake = v * interval
        uptake = min(uptake, max(local, 0.0))        # cannot remove more than is there
        biomass_gain = c["yield_coef"] * uptake

        # chemotaxis up the local concentration gradient (central difference)
        right = field[idx + 1] if idx < n - 1 else field[idx]
        left = field[idx - 1] if idx > 0 else field[idx]
        grad = 0.5 * (right - left)
        step = c["chemotaxis"] * grad * interval
        step = max(-c["max_step"], min(c["max_step"], step))
        # keep the cell inside the domain
        if x + step < 0: step = -x
        if x + step > n - 1: step = (n - 1) - x

        sink = [0.0] * n
        sink[idx] = -uptake

        return {
            "chemical_field": _delta_map(sink),
            "position": step,
            "biomass": biomass_gain,
            "uptake": self._set("uptake", uptake),
            "uptake_total": uptake,          # additive → cumulative Σ uptake
            "local_conc": self._set("local_conc", local),
            "gradient": self._set("gradient", grad),
        }
