"""GrayScott -- Task 2 of study 5 `molecular-interfaces`: wraps the Task-1
physics spike (`tests/test_gray_scott_physics.py`) as a `fields`-store
process, emitting the pattern-formation metric (`v_var`, `n_domains`) plus a
gated `patterned` flag, with an optional thermal (Arrhenius) rate-modulation
channel.

Physics (LIFTED, unchanged, from Task 1): local autocatalytic chemistry
(`U + 2V -> 3V`, `V -> P`) plus differential diffusion (`Dv < Du`) turns a
near-uniform noisy seed into an emergent Turing spot pattern --

    du/dt = Du*lap(u) - rate*u*v**2 + F*(1-u)
    dv/dt = Dv*lap(v) + rate*u*v**2 - (F+k)*v

`lap` is the periodic 5-point Laplacian (`dx=1`, same as
`condensate/cahn_hilliard.py`'s `laplacian`/`protocell/autopoiesis.py`'s
`laplacian`). Canonical spot regime: `Du=0.16, Dv=0.08, F=0.037, k=0.06`,
`dt=1.0` (explicit Euler); CFL: `Du*dt*4 = 0.64 < 1` -- stable (verified in
the Task-1 api-map and re-checked at construction time below).
`laplacian`/`gs_step`/`seed_uv`/`run_gs`/`v_var`/`n_domains` are verbatim
copies of the Task-1 spike's module-level functions, with ONE extension:
`gs_step` gains an optional elementwise `rate` multiplier (default `1.0`,
identical behavior to the Task-1 spike when omitted) on the `u*v**2`
reaction term -- this is the thermal channel's hook.

Thermal channel: when a `temperature` field is present in the store, the
reaction term is scaled by the elementwise Arrhenius rate factor
`rate = exp(-Ea*(1/T - 1/Tref))` (T > Tref speeds the reaction up, T < Tref
slows it down; `rate == 1` when `T == Tref`). `Ea`/`Tref` are accepted in
the config unconditionally but only take effect when a `temperature` field
is actually present -- with no such field, `rate = 1.0` everywhere and the
process is pure chemistry, identical to the Task-1 spike.

Metric: `v_var = v.var()` (spatial variance of the inhibitor field) --
seed-robust per the Task-1 api-map and the primary pass/fail signal.
Secondary: `n_domains = scipy.ndimage.label(v > thr)[1]` (connected
`v`-concentration domains). `patterned` gates on `v_var > PATTERN_FLOOR`, a
fixed floor between the near-uniform seed/controls' `v_var` (~0, exactly 0.0
for the equal-diffusion control per the Task-1 api-map) and the patterned
run's `v_var` (~0.0117 at 8000 steps, canonical params) -- NOT exposed in
the config (mirrors `protocell/autopoiesis.py`'s `MASS_FLOOR_FRAC`).

Field coupling: `fields` is the same additive `map[array]` store used by
`condensate/cahn_hilliard.py`'s `CahnHilliard` and
`protocell/autopoiesis.py`'s `Protocell` -- process-bigraph's engine SUMS
emitted arrays into it. So `update()` reads the CURRENT `u`/`v` out of the
store, advances local copies `steps_per_tick` times, and emits the DELTA
(`u_new - u_read`, `v_new - v_read`), never the full new field (which would
double it every tick). `temperature`, when present, is read-only here (no
delta emitted for it -- this process never writes it).
"""
from __future__ import annotations

import numpy as np
from process_bigraph import Process
from scipy import ndimage

N = 128
DU, DV, F, K = 0.16, 0.08, 0.037, 0.06
DT = 1.0
DOMAIN_THRESHOLD = 0.2

# Fixed floor between the near-uniform seed/controls' v_var (~0, exactly 0.0
# for the equal-diffusion control per the Task-1 api-map) and the patterned
# run's v_var (~0.0117 at 8000 steps, canonical params) -- see module
# docstring. Not exposed in the config, mirrors Protocell's MASS_FLOOR_FRAC.
PATTERN_FLOOR = 0.002


def _f(default):
    return {"_type": "float", "_default": default}


def laplacian(f):
    """Periodic 5-point Laplacian on a 2D array, grid spacing dx=1 (same as
    `condensate/cahn_hilliard.py`'s `laplacian`)."""
    return (
        np.roll(f, 1, axis=0) + np.roll(f, -1, axis=0)
        + np.roll(f, 1, axis=1) + np.roll(f, -1, axis=1)
        - 4.0 * f
    )


def gs_step(u, v, Du, Dv, F, k, dt=DT, react=True, rate=1.0):
    """One explicit-Euler Gray-Scott update step. Returns (u_new, v_new).

    `react=False` is the reaction-off knockout: it drops the `u*v**2`
    autocatalysis term from BOTH equations entirely, leaving pure diffusion
    plus the feed/removal terms. `rate` (scalar or elementwise array) scales
    the reaction term -- the thermal channel's hook (see module docstring);
    `rate=1.0` (the default) reproduces the Task-1 spike's pure-chemical
    physics exactly.
    """
    uvv = rate * u * v * v if react else 0.0
    u_new = u + dt * (Du * laplacian(u) - uvv + F * (1.0 - u))
    v_new = v + dt * (Dv * laplacian(v) + uvv - (F + k) * v)
    return u_new, v_new


def seed_uv(n=N, seed=1, noise=0.02, n_patches=5, patch_size=6, patch_u=0.50, patch_v=0.25):
    """Near-uniform seed: u~=1, v~=0 plus small Gaussian noise, plus a few
    small square nucleation patches of elevated v (and depleted u) -- without
    these patches the reaction term u*v**2 is ~0 everywhere and nothing ever
    nucleates. Deterministic given `seed`.
    """
    rng = np.random.default_rng(seed)
    u = np.ones((n, n)) + noise * rng.standard_normal((n, n))
    v = np.zeros((n, n)) + noise * rng.standard_normal((n, n))
    half = patch_size // 2
    for _ in range(n_patches):
        cx = int(rng.integers(0, n))
        cy = int(rng.integers(0, n))
        xs = np.arange(cx - half, cx + half) % n
        ys = np.arange(cy - half, cy + half) % n
        u[np.ix_(xs, ys)] = patch_u
        v[np.ix_(xs, ys)] = patch_v
    return u, v


def run_gs(u0, v0, Du, Dv, F, k, steps, dt=DT, react=True, rate=1.0):
    """Advance (u0, v0) `steps` explicit-Euler steps. Returns final (u, v)."""
    u, v = u0.copy(), v0.copy()
    for _ in range(steps):
        u, v = gs_step(u, v, Du, Dv, F, k, dt=dt, react=react, rate=rate)
        assert np.all(np.isfinite(u)) and np.all(np.isfinite(v))
    return u, v


def v_var(v):
    return float(np.asarray(v).var())


def n_domains(v, thr=DOMAIN_THRESHOLD):
    _labeled, count = ndimage.label(np.asarray(v) > thr)
    return int(count)


class GrayScott(Process):
    """Wraps `gs_step` as a `fields`-store process. See module docstring."""

    config_schema = {
        # NOTE: no `_default` on `grid` (a `map[integer]`) -- bigraph-schema's
        # generic container "map" apply merges a schema-declared `_default`
        # with an incoming config value on composition rather than replacing
        # it (same trap documented in `cpm/sorting.py`,
        # `condensate/cahn_hilliard.py`, and `protocell/autopoiesis.py`);
        # Python-side defaulting in `__init__` avoids it. `grid` is
        # informational/validating only -- the process reads the field's
        # actual shape from the store every tick, it never allocates `u`/`v`
        # itself.
        "grid": {"_type": "map[integer]"},
        # Canonical spot-regime params, pinned per the Task-1 physics spike.
        "Du": _f(DU),
        "Dv": _f(DV),
        "F": _f(F),
        "k": _f(K),
        "dt": _f(DT),
        "steps_per_tick": {"_type": "integer", "_default": 50},
        # Domain-count threshold (`n_domains`'s `v > thr` label mask) --
        # matches the Task-1 spike's DOMAIN_THRESHOLD default.
        "thr": _f(DOMAIN_THRESHOLD),
        # Reserved for a future stochastic-seeding variant -- the current
        # gs_step physics is fully deterministic (no RNG); kept in the
        # schema per the Task-2 interface spec so callers can pin it now
        # (mirrors Protocell's currently-inert `seed`).
        "seed": {"_type": "integer", "_default": 1},
        # Thermal (Arrhenius) channel -- only take effect when a
        # `temperature` field is present in the store (see module
        # docstring); accepted unconditionally so a composite can pin them
        # ahead of adding the field.
        "Ea": _f(0.0),
        "Tref": _f(1.0),
    }

    def inputs(self):
        return {"fields": "map[array]"}

    def outputs(self):
        # `fields` is a genuine spatial DELTA the engine sums into the shared
        # grid (see module docstring) -- plain `map[array]` is correct
        # there. The observables below are absolute readings of the new
        # field/run state, not deltas, so they must be `overwrite[...]`
        # (replace-on-apply) or a multi-tick run would sum them into
        # nonsense -- same reasoning as `CahnHilliard`'s `phi_var` etc. and
        # `Protocell`'s `enclosed_area` etc.
        return {
            "fields": "map[array]",
            "v_var": "overwrite[float]",
            "n_domains": "overwrite[float]",
            "patterned": "overwrite[float]",
        }

    def __init__(self, config=None, core=None):
        raw_config = dict(config) if config else {}
        super().__init__(config, core=core)
        c = dict(self.config)
        # bigraph-schema's `core.fill` merge treats a Float/Integer value
        # equal to 0 as "empty" (`is_empty`) and silently refills it from the
        # schema `_default` -- so an explicitly-passed `Ea=0.0` (disabling
        # the thermal channel even with a `temperature` field present) or any
        # other legitimate 0 would otherwise be clobbered back to its
        # non-zero default. Restore whatever the caller actually passed for
        # every scalar config key (mirrors Protocell's identical guard).
        for key in ("Du", "Dv", "F", "k", "dt", "steps_per_tick", "thr", "seed", "Ea", "Tref"):
            if key in raw_config:
                c[key] = raw_config[key]
        self.config = c
        self._Du = float(c["Du"])
        self._Dv = float(c["Dv"])
        self._F = float(c["F"])
        self._k = float(c["k"])
        self._dt = float(c["dt"])
        self._steps = int(c["steps_per_tick"])
        self._thr = float(c["thr"])
        self._seed = int(c.get("seed", 1))
        self._Ea = float(c["Ea"])
        self._Tref = float(c["Tref"])

        # CFL guard: classic 2D explicit-diffusion stability, D*dt <= 0.25
        # (dx=1) i.e. D*dt*4 < 1, checked against whichever of Du/Dv is
        # larger. Raise loudly at construction time (config is fully known
        # here) rather than letting an unstable config run silently toward
        # NaN -- mirrors CahnHilliard's/Protocell's stiffness/CFL guards.
        cfl = max(self._Du, self._Dv) * self._dt * 4.0
        if not (cfl < 1.0):
            raise ValueError(
                f"GrayScott: max(Du,Dv)*dt*4 = {cfl:.4g} >= 1 violates the "
                f"explicit 2D reaction-diffusion CFL stability limit "
                f"(D*dt <= 0.25, dx=1). Du={self._Du}, Dv={self._Dv}, "
                f"dt={self._dt}. The pinned canonical Du=0.16, Dv=0.08, "
                f"dt=1.0 gives max(Du,Dv)*dt*4=0.64, comfortably stable -- a "
                f"larger Du/Dv or dt is the likely cause, not a data/config "
                f"bug elsewhere."
            )

    def update(self, state, interval):
        fields = state.get("fields", {}) or {}
        u0 = np.array(fields.get("u"), dtype=float, copy=True)
        v0 = np.array(fields.get("v"), dtype=float, copy=True)
        temperature = fields.get("temperature", None)

        if temperature is not None:
            T = np.asarray(temperature, dtype=float)
            # Elementwise Arrhenius rate factor: T > Tref speeds the
            # reaction up, T < Tref slows it down, T == Tref -> rate == 1.
            rate = np.exp(-self._Ea * (1.0 / T - 1.0 / self._Tref))
        else:
            rate = 1.0

        u, v = u0, v0
        for _ in range(self._steps):
            u, v = gs_step(u, v, self._Du, self._Dv, self._F, self._k,
                            dt=self._dt, rate=rate)

        if not (np.all(np.isfinite(u)) and np.all(np.isfinite(v))):
            raise FloatingPointError(
                f"GrayScott: u/v went non-finite (NaN/Inf) after {self._steps} "
                f"steps at Du={self._Du}, Dv={self._Dv}, F={self._F}, "
                f"k={self._k}, dt={self._dt}. The CFL guard at construction "
                f"should prevent this for max(Du,Dv)*dt*4 < 1 -- if you are "
                f"seeing this, re-check for an unusually extreme seed field "
                f"or thermal rate factor, not the diffusion stability limit."
            )

        var = float(v.var())
        n_dom = n_domains(v, thr=self._thr)
        patterned = 1.0 if var > PATTERN_FLOOR else 0.0

        return {
            "fields": {"u": u - u0, "v": v - v0},
            "v_var": var,
            "n_domains": float(n_dom),
            "patterned": patterned,
        }
