"""FieldPointCoupling — a field↔point adapter that lets the UNCHANGED cellular
interface run on a real 2D chemical field.

The cellular-interface study's fig04 composites are *lumped*: the
:class:`~meta_modelers_guide.handlers_fig03b.CellularInterfaceHandler` senses a
single scalar ``chemical_ext`` (a concentration) and returns a scalar
``chemical`` flux (net uptake, ``-uptake_rate·chemical_ext`` — negative). This
adapter is the *spatial translation*: it sits between that handler's chemical
port and a spatio-flux :class:`DiffusionAdvection` chemical field, and does the
two-way coarse-grain the handler cannot do itself:

* **field → point (sense):** sample the field's mean concentration over a small
  circular footprint around the cell's location and expose it as the scalar
  ``local`` the handler reads as ``chemical_ext``. Because the field carries a
  spatial gradient, this sensed value is *spatially determined* — move the cell
  and it senses a different concentration.
* **point → field (act):** take the handler's scalar ``chemical`` flux (net
  uptake, negative) and deposit it back into the footprint cells as a field
  *delta* — depleting the field exactly where the cell takes up nutrient
  (niche construction). One-step lag on the flux is fine: on the first tick the
  handler hasn't produced a flux yet, so nothing is removed.

The whole point is *substrate-independence*: the handler's ``inputs``/``outputs``
contract is byte-identical to the lumped fig04 run — only the process composed
behind its chemical port has changed (a spatial diffusion field instead of a
constant store). Mechanical, electrical and thermal remain lumped; only the
chemical modality is spatialized here.

Field-read and delta-write mechanics mirror the tested flagship
``CpmCellField`` (``meta_modelers_guide/cpm/cell_field.py``): read the field over
a footprint mask, and write the uptake back proportional to each pixel's own
current value (so a low pixel gives up proportionally less and can never be
driven negative), clamped to what the footprint actually holds.
"""
from __future__ import annotations

import numpy as np
from process_bigraph import Process


def _f(default):
    return {"_type": "float", "_default": default}


def _i(default):
    return {"_type": "integer", "_default": default}


class FieldPointCoupling(Process):
    """Adapter coupling a scalar cellular-interface chemical port to a 2D field.

    Ports (what makes it a field↔point adapter):

    * inputs ``field`` (the 2D chemical field, wired to ``['fields','chemical']``)
      and ``flux`` (the interface's ``chemical`` output — net uptake, negative —
      wired to ``['interface','chemical']``).
    * outputs ``local`` (scalar footprint-mean concentration, wired to
      ``['environment','chemical']`` — the handler's ``chemical_ext``) and
      ``field`` (a spatial delta summed back into ``['fields','chemical']``).
    """

    config_schema = {
        "nx": _i(40),
        "ny": _i(40),
        # cell footprint center in grid-index space; non-zero on purpose — a
        # scalar config value of exactly 0 is silently refilled from the schema
        # _default by bigraph-schema (the zero-config trap), so a 0 coordinate
        # would be unreliable. Center of the default 40x40 grid.
        "cx": _i(20),
        "cy": _i(20),
        "radius": _f(4.0),          # footprint radius (grid cells)
        "species": {"_type": "string", "_default": "chemical"},
        # `active` gates the uptake writeback. It is a BOOLEAN rather than a
        # 0/1 float precisely to sidestep the zero-config trap: a float 0.0 here
        # would be silently replaced by its schema default. Left True for the
        # normal coupled run; a control variant can set it False to sense-only.
        "active": {"_type": "boolean", "_default": True},
    }

    def inputs(self):
        return {
            "field": "array",           # the 2D chemical field at ['fields','chemical']
            "flux": "chemical_flux",    # interface's chemical output (net uptake, <=0)
        }

    def outputs(self):
        return {
            "local": "concentration",   # footprint-mean, -> environment.chemical
            "field": "array",           # spatial delta summed into ['fields','chemical']
        }

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core)
        c = self.config
        self._nx, self._ny = int(c["nx"]), int(c["ny"])
        self._active = bool(c["active"])
        # Precompute the circular footprint mask once (location is fixed).
        yy, xx = np.mgrid[0:self._ny, 0:self._nx]
        r = float(c["radius"])
        self._fp = ((xx - int(c["cx"])) ** 2 + (yy - int(c["cy"])) ** 2) <= r * r
        if not self._fp.any():  # radius too small — fall back to the single center cell
            self._fp[int(c["cy"]), int(c["cx"])] = True
        self._area = int(self._fp.sum())
        # set-semantics bookkeeping for the `local` (concentration) port: the store
        # accumulates deltas, so emit the delta that carries it to the sampled mean.
        self._last_local = 0.0

    def update(self, state, interval):
        field = np.asarray(state.get("field"), dtype=float)
        fp = self._fp

        # --- field -> point (sense): mean concentration over the footprint -------
        local = float(field[fp].mean()) if fp.any() else 0.0
        d_local = local - self._last_local     # set-delta onto the additive store
        self._last_local = local

        # --- point -> field (act): deposit the interface's uptake flux -----------
        # `flux` is the handler's `chemical` output: net uptake, <= 0. Deposit it
        # into the footprint as a depletion delta, distributed proportional to each
        # pixel's current concentration and clamped to what the footprint holds, so
        # no pixel can be driven negative (mirrors CpmCellField's writeback).
        flux = float(state.get("flux", 0.0))
        dfield = np.zeros_like(field)
        if self._active and flux < 0.0 and fp.any():
            requested = flux * interval                        # <= 0 total removal
            available = -float(field[fp].sum())                # <= 0 (max removable)
            clamped = max(requested, available)                # not more than present
            fp_vals = field[fp]
            total = float(fp_vals.sum())
            weights = (fp_vals / total) if total > 0 else np.full(self._area, 1.0 / self._area)
            dfield[fp] = clamped * weights

        return {"local": d_local, "field": dfield}
