"""Protocell -- Task 2 of study 7 `autopoiesis`: wraps the Task-1 physics
spike (`tests/test_protocell_physics.py`) as a `fields`-store process,
emitting the boundary-integrity metric (`enclosed_area`) plus a gated
`persists` flag.

Physics (LIFTED, unchanged, from Task 1): a scalar membrane-density field
`phi` on a periodic grid under

    dphi/dt = D*lap(phi) - k_decay*phi + production

`production` fires only where the membrane still topologically encloses an
interior (`binary_fill_holes(phi > thr) & ~(phi > thr)`), is deposited onto
existing membrane (prop to phi), and is throttled by the enclosed area
relative to a fixed reference area (self-limiting -- homeostasis, not
runaway growth). `laplacian`/`enclosed_area`/`seed_annulus`/`rd_step` below
are verbatim copies of the Task-1 spike's module-level functions; see that
module's docstring for the full derivation and canonical params
(D=0.02, k_decay=0.01, k_prod=0.03, thr=0.30).

Homeostasis here is METASTABLE, not perpetual (Task-1 ruling, carried
forward): the closed loop self-maintains over a bounded window (empirically
stable through ~2000 steps, comfortable margin before the ~2450-2650-step
range where the ring eventually breaks down even with production on). This
process and its tests are only ever run/asserted within that ~2000-step
window -- that is the accepted, honestly-framed signature of a closed toy
system, not a bug to chase.

Field coupling: `fields` is the same additive `map[array]` store used by
`condensate/cahn_hilliard.py`'s `CahnHilliard` -- process-bigraph's engine
SUMS emitted arrays into it. So `update()` reads the CURRENT `phi` out of the
store, advances a local copy `steps_per_tick` times, and emits the DELTA
(`phi_new - phi_read`), never the full new field (which would double it every
tick). See that module's docstring for the details verified in
`tests/test_cpm_colony_two_writer.py`.

`persists` gate: `enclosed_area > 0` alone cannot distinguish a genuinely
persisting vesicle from a degenerate case where the interior has been
filled in solid (also `area == 0` once filled, so actually the topological
metric already rejects a filled blob) or from a vanishingly thin/underfed
membrane. Per the Task-1 api-map's open risk #2, this process ANDs
`enclosed_area > 0` with `membrane_mass > mass_floor` (a small fraction of
the seed's own mass) so a technically-closed but starved boundary is not
misread as alive.
"""
from __future__ import annotations

import numpy as np
from process_bigraph import Process
from scipy.ndimage import binary_fill_holes

# Small fraction of the seed's own mass used as the `persists` mass floor --
# see module docstring / Task-1 api-map open risk #2. Chosen well below the
# Task-1 physics test's observed homeostatic-plateau mass range
# (0.4x-2.5x seed mass) and well above the negative control's post-collapse
# mass (< 5.0, decaying toward 0), so it discriminates the two regimes
# cleanly without being sensitive to the exact fraction chosen.
MASS_FLOOR_FRAC = 0.05


def _f(default):
    return {"_type": "float", "_default": default}


def laplacian(phi):
    """Periodic 5-point Laplacian on a 2D array, grid spacing dx=1 (same as
    `condensate/cahn_hilliard.py`'s `laplacian`)."""
    return (
        np.roll(phi, 1, axis=0) + np.roll(phi, -1, axis=0)
        + np.roll(phi, 1, axis=1) + np.roll(phi, -1, axis=1)
        - 4.0 * phi
    )


def enclosed_area(phi, thr=0.30):
    """Boundary-integrity / closure detector. Returns the boolean interior
    mask (`binary_fill_holes(phi > thr) & ~(phi > thr)`); `.sum()` is the
    enclosed-area metric in pixels. A closed ring encloses its center (mask
    nonempty); any gap in the ring leaks to the grid border and
    `binary_fill_holes` returns the membrane only (mask empty, area == 0)."""
    membrane = phi > thr
    return binary_fill_holes(membrane) & ~membrane


def seed_annulus(n=64, r0=None, sigma=2.5, amp=1.0):
    """Deterministic Gaussian-annulus seed -- a closed membrane ring."""
    r0 = n / 4.0 if r0 is None else r0
    yy, xx = np.mgrid[0:n, 0:n]
    cy, cx = n / 2.0, n / 2.0
    r = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    return amp * np.exp(-((r - r0) ** 2) / (2 * sigma ** 2))


def rd_step(phi, D, k_decay, k_prod, area_ref, thr=0.30, dt=1.0):
    """One explicit reaction-diffusion protocell update:

        phi_new = phi + dt*(D*lap(phi) - k_decay*phi + production)

    `production = k_prod * phi * min(1, area/area_ref)` where `area` is the
    current enclosed-interior pixel count -- zero whenever the membrane does
    not enclose an interior (the closure gate), and throttled by the
    enclosed area relative to `area_ref` (normally the seed's own enclosed
    area) so the loop self-limits into a homeostatic plateau rather than
    growing without bound. `k_prod=0` collapses this to plain
    decay+diffusion (the negative-control knockout)."""
    lap = laplacian(phi)
    if k_prod > 0:
        area = int(enclosed_area(phi, thr).sum())
        if area > 0:
            scale = min(1.0, area / area_ref)
            production = k_prod * phi * scale
        else:
            production = 0.0
    else:
        production = 0.0
    return phi + dt * (D * lap - k_decay * phi + production)


class Protocell(Process):
    """Wraps `rd_step` as a `fields`-store process. See module docstring."""

    config_schema = {
        # NOTE: no `_default` on `grid` (a `map[integer]`) -- bigraph-schema's
        # generic container "map" apply merges a schema-declared `_default`
        # with an incoming config value on composition rather than replacing
        # it (same trap documented in `cpm/sorting.py` and
        # `condensate/cahn_hilliard.py`); Python-side defaulting in
        # `__init__` avoids it. `grid` is informational/validating only --
        # the process reads the field's actual shape from the store every
        # tick, it never allocates `phi` itself.
        "grid": {"_type": "map[integer]"},
        # Canonical params, pinned per the Task-1 physics spike.
        "D": _f(0.02),
        "k_decay": _f(0.01),
        "k_prod": _f(0.03),
        "thr": _f(0.30),
        "dt": _f(1.0),
        "steps_per_tick": {"_type": "integer", "_default": 50},
        # Reserved for a future stochastic seed variant -- the current
        # `rd_step`/`seed_annulus` physics is fully deterministic (no RNG),
        # so this is accepted but currently inert; kept in the schema per
        # the Task-2 interface spec so callers can pin it now.
        "seed": {"_type": "integer", "_default": 1},
    }

    def inputs(self):
        return {"fields": "map[array]"}

    def outputs(self):
        # `fields` is a genuine spatial DELTA the engine sums into the shared
        # grid (see module docstring) -- plain `map[array]` is correct
        # there. The observables below are absolute readings of the new
        # field/run state, not deltas, so they must be `overwrite[...]`
        # (replace-on-apply) or a multi-tick run would sum them into
        # nonsense -- same reasoning as `CahnHilliard`'s `phi_var` etc.
        return {
            "fields": "map[array]",
            "enclosed_area": "overwrite[float]",
            "membrane_mass": "overwrite[float]",
            "persists": "overwrite[float]",
            "collapse_tick": "overwrite[float]",
        }

    def __init__(self, config=None, core=None):
        raw_config = dict(config) if config else {}
        super().__init__(config, core=core)
        c = dict(self.config)
        # bigraph-schema's `core.fill` merge treats a Float/Integer value
        # equal to 0 as "empty" (`is_empty`) and silently refills it from
        # the schema `_default` -- so an explicitly-passed `k_prod=0.0`
        # (the negative-control knockout) or any other legitimate 0 would
        # otherwise be clobbered back to its non-zero default. Restore
        # whatever the caller actually passed for every scalar config key.
        for key in ("D", "k_decay", "k_prod", "thr", "dt", "steps_per_tick", "seed"):
            if key in raw_config:
                c[key] = raw_config[key]
        self.config = c
        self._D = float(c["D"])
        self._k_decay = float(c["k_decay"])
        self._k_prod = float(c["k_prod"])
        self._thr = float(c["thr"])
        self._dt = float(c["dt"])
        self._steps = int(c["steps_per_tick"])
        self._seed = int(c.get("seed", 1))

        # CFL guard: classic 2D explicit-diffusion stability, D*dt <= 0.25
        # (dx=1) i.e. D*dt*4 < 1. Raise loudly at construction time (config
        # is fully known here) rather than letting an unstable config run
        # silently toward NaN -- mirrors CahnHilliard's stiffness guard.
        cfl = self._D * self._dt * 4.0
        if not (cfl < 1.0):
            raise ValueError(
                f"Protocell: D*dt*4 = {cfl:.4g} >= 1 violates the explicit "
                f"2D reaction-diffusion CFL stability limit (D*dt <= 0.25, "
                f"dx=1). D={self._D}, dt={self._dt}. The pinned canonical "
                f"D=0.02, dt=1.0 gives D*dt*4=0.08, comfortably stable -- a "
                f"larger D or dt is the likely cause, not a data/config bug "
                f"elsewhere."
            )

        # `area_ref` is fixed at the ENCLOSED AREA OF THE FIRST phi THIS
        # PROCESS EVER READS (i.e. the seed), computed lazily on the first
        # `update()` call and then held fixed for the process's lifetime --
        # mirrors the Task-1 physics test's `seed_area`, which is computed
        # once from `phi0` and reused as `area_ref` on every subsequent
        # `rd_step` call, across ticks.
        self._area_ref = None
        self._mass_floor = None

        # Tracks the FIRST internal RD step (counted across this process's
        # entire lifetime, not per-tick) at which `enclosed_area` hits 0;
        # -1 while it never has. Finer-grained than the outer tick count so
        # a fast collapse (e.g. within one `steps_per_tick` window) is still
        # located precisely, matching the Task-1 physics test's per-step
        # `collapse_step` tracking.
        self._step_count = 0
        self._collapse_tick = -1

    def update(self, state, interval):
        fields = state.get("fields", {}) or {}
        phi0 = np.array(fields.get("phi"), dtype=float, copy=True)

        if self._area_ref is None:
            seed_area = int(enclosed_area(phi0, self._thr).sum())
            # Guard against a degenerate seed (no enclosed interior at all)
            # dividing by zero in `rd_step`'s `area/area_ref` scale below.
            self._area_ref = seed_area if seed_area > 0 else 1
            self._mass_floor = MASS_FLOOR_FRAC * float(phi0.sum())

        phi = phi0
        for _ in range(self._steps):
            phi = rd_step(
                phi, self._D, self._k_decay, self._k_prod, self._area_ref,
                thr=self._thr, dt=self._dt,
            )
            self._step_count += 1
            if self._collapse_tick == -1 and int(enclosed_area(phi, self._thr).sum()) == 0:
                self._collapse_tick = self._step_count

        if not np.all(np.isfinite(phi)):
            raise FloatingPointError(
                f"Protocell: phi went non-finite (NaN/Inf) after {self._steps} "
                f"internal steps at D={self._D}, dt={self._dt}, "
                f"k_decay={self._k_decay}, k_prod={self._k_prod}. The CFL "
                f"guard at construction should prevent this for D*dt*4 < 1 -- "
                f"if you are seeing this, re-check for an unusually extreme "
                f"seed field, not the diffusion stability limit."
            )

        area = int(enclosed_area(phi, self._thr).sum())
        mass = float(phi.sum())
        persists = 1.0 if (area > 0 and mass > self._mass_floor) else 0.0

        delta = phi - phi0
        return {
            "fields": {"phi": delta},
            "enclosed_area": float(area),
            "membrane_mass": mass,
            "persists": persists,
            "collapse_tick": float(self._collapse_tick),
        }
