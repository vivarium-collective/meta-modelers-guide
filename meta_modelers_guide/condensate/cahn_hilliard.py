"""CahnHilliard -- an independent, uncoupled condensate-phase-separation analogue:
a scalar field phi undergoes spinodal decomposition under Cahn-Hilliard dynamics,
mass-conserved. It does NOT touch the CPM cells (`CpmSorting`) or any dFBA/cobra
path at all -- pure numpy over a `fields` store, honestly framed as an independent
uncoupled process, not a mechanistic model of a specific biomolecular condensate.

Physics: `mu = phi**3 - phi - kappa*lap(phi)` (chemical potential -- a double-well
free energy `phi**4/4 - phi**2/2` plus a `kappa`-weighted interfacial-gradient
penalty), `phi = phi + dt*M*lap(mu)` (Cahn-Hilliard: mass-conserving relaxation
down the mu gradient). `lap` is the periodic 5-point Laplacian (`dx=1`).

Stability: the explicit `lap(lap(phi))` (biharmonic, `nabla^4`) term this scheme
implies makes it numerically stiff. Verified API-map run: `M=1.0, kappa=0.5,
dt=0.002` is stable over ~20000 total steps (spinodal decomposition completes,
`phi_var` ~0.0002 -> ~0.5, no NaN); `dt=0.05` blows up to NaN within a few
thousand steps at the same `M`/`kappa`. The stability limit is approximately
`dt < dx**4 / (16*M*kappa)`. `dt` is PINNED at 0.002 here -- do not raise it
without re-verifying against a real run.

Field coupling: `fields` is a shared `map[array]` store that process-bigraph's
engine SUMS emitted arrays into (additive apply -- verified for two independent
writers in `tests/test_cpm_colony_two_writer.py`, and used the same way by
`CpmCellField`/`CpmColonyField`'s glucose/acetate deltas in `cpm/cell_field.py`
and `cpm/colony_field.py`). So `update()` reads the CURRENT `phi` out of the
store, advances a local copy `steps_per_tick` times, and emits the DELTA
(`phi_new - phi_read`), not the full new field -- emitting the full field would
be summed onto the old one and double it every tick.
"""
from __future__ import annotations

import numpy as np
from process_bigraph import Process


def _f(default):
    return {"_type": "float", "_default": default}


def laplacian(f):
    """Periodic 5-point Laplacian on a 2D array, grid spacing dx=1."""
    return (
        np.roll(f, 1, axis=0) + np.roll(f, -1, axis=0)
        + np.roll(f, 1, axis=1) + np.roll(f, -1, axis=1)
        - 4.0 * f
    )


def ch_step(phi, M, kappa, dt):
    """One explicit Cahn-Hilliard update step. Returns the new phi array."""
    mu = phi ** 3 - phi - kappa * laplacian(phi)
    return phi + dt * M * laplacian(mu)


class CahnHilliard(Process):
    config_schema = {
        # NOTE: no `_default` on `grid` (a `map[integer]`) -- bigraph-schema's
        # generic container "map" apply merges a schema-declared `_default` with
        # an incoming config value on composition rather than replacing it (same
        # trap documented in `cpm/sorting.py`'s `grid`/`checkerboard`/`cells`
        # NOTE); Python-side defaulting in `__init__` avoids it. `grid` here is
        # informational/validating only -- the process reads the field's actual
        # shape from the store every tick, it never allocates `phi` itself.
        "grid": {"_type": "map[integer]"},
        "M": _f(1.0),
        "kappa": _f(0.5),
        # PINNED stability-verified default -- see module docstring. A caller
        # raising this without re-verifying risks silent-looking NaN blowup,
        # which `update()` below guards against by raising loudly instead.
        "dt": _f(0.002),
        "steps_per_tick": {"_type": "integer", "_default": 50},
    }

    def inputs(self):
        return {"fields": "map[array]"}

    def outputs(self):
        # `fields` is a genuine spatial DELTA the engine sums into the shared
        # grid (see module docstring) -- plain `map[array]` is correct there.
        # `phi_var`/`phi_mean`/`phi_min`/`phi_max` are this tick's absolute
        # readings of the new field, not deltas, so they must be
        # `overwrite[...]` (replace-on-apply) or a multi-tick run would sum them
        # into nonsense -- same reasoning as `CpmSorting`'s absolute observables
        # and `CpmCellField`'s `volume`/`position`.
        return {
            "fields": "map[array]",
            "phi_var": "overwrite[float]",
            "phi_mean": "overwrite[float]",
            "phi_min": "overwrite[float]",
            "phi_max": "overwrite[float]",
        }

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core)
        c = self.config
        self._M = float(c["M"])
        self._kappa = float(c["kappa"])
        self._dt = float(c["dt"])
        self._steps = int(c["steps_per_tick"])

    def update(self, state, interval):
        fields = state.get("fields", {}) or {}
        phi0 = np.array(fields.get("phi"), dtype=float, copy=True)

        phi = phi0
        for _ in range(self._steps):
            phi = ch_step(phi, self._M, self._kappa, self._dt)

        if not np.all(np.isfinite(phi)):
            limit = 1.0 / (16.0 * self._M * self._kappa) if self._M * self._kappa else float("nan")
            raise FloatingPointError(
                f"CahnHilliard: phi went non-finite (NaN/Inf) after {self._steps} "
                f"steps at dt={self._dt}, M={self._M}, kappa={self._kappa}. The "
                f"explicit nabla^4 term is stiff; the approximate stability limit "
                f"is dt < dx^4/(16*M*kappa) ~= {limit:.4g} (dx=1). The pinned "
                f"default dt=0.002 is verified stable over ~20000 steps -- a "
                f"larger dt is the likely cause, not a data/config bug elsewhere."
            )

        delta = phi - phi0
        return {
            "fields": {"phi": delta},
            "phi_var": float(phi.var()),
            "phi_mean": float(phi.mean()),
            "phi_min": float(phi.min()),
            "phi_max": float(phi.max()),
        }
