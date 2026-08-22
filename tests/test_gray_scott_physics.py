"""Gray-Scott reaction-diffusion -- pure-physics spike proving the chemical
molecular channel made SPATIAL: local autocatalytic chemistry (`U + 2V -> 3V`,
`V -> P`) plus DIFFERENTIAL diffusion (`Dv < Du`) turns a near-uniform noisy
seed into an emergent Turing spot pattern. No process-bigraph engine here --
this is the RED/GREEN physics-only spike (see
`docs/superpowers/api-maps/2026-08-21-molecular-interfaces-api-map.md`). The
`step`/seed-builder/metrics below are MODULE-LEVEL so Task 2 can lift them
directly into `meta_modelers_guide/molecular/gray_scott.py` (the field
process), mirroring how `condensate/cahn_hilliard.py` factors `ch_step` out
of its `CahnHilliard` process.

Physics: `du/dt = Du*lap(u) - u*v**2 + F*(1-u)`, `dv/dt = Dv*lap(v) +
u*v**2 - (F+k)*v`. `lap` is the periodic 5-point Laplacian (`dx=1`, same as
`cahn_hilliard.laplacian`). Canonical spot regime: `Du=0.16, Dv=0.08,
F=0.037, k=0.06`, 128x128 periodic grid, `dt=1.0` (explicit Euler). CFL:
`Du*dt*4 = 0.64 < 1` -- stable (verified in the API map).

Seed: `u~=1, v~=0` plus ~2% Gaussian noise, plus a handful of small square
nucleation patches of elevated `v` (classic Gray-Scott seeding -- a fully
flat `v=0` never nucleates because the `u*v**2` term is identically zero
everywhere). Deterministic via `np.random.default_rng(1)`.

Metric: `v_var = v.var()` (spatial variance of the inhibitor field) --
seed-robust per the API map (`[0.01163, 0.01191]` across seeds 1-5) and the
primary pass/fail signal. Secondary: `n_domains =
scipy.ndimage.label(v > thr)[1]` (connected `v`-concentration domains,
seed-sensitive -- reported/asserted only as "more than one", not pinned).

Verified numbers (API map, ~8000 steps, seed=1): reaction ON (`Du=0.16,
Dv=0.08`) -> `v_var` 0.00257 -> ~0.0117, ~11 domains (PATTERNED). Both
controls below drive `v_var` to exactly 0.0 (UNIFORM):
  - equal-diffusion control (`Du=Dv=0.12`, chemistry fully ON) -- the
    load-bearing causal control: removes ONLY differential diffusion,
    isolating diffusion-driven (Turing) instability as the cause of
    structure.
  - reaction-off control (drop the `u*v**2` autocatalysis term entirely) --
    a simpler secondary cross-check; `v` just relaxes toward 0 under its own
    removal term `-(F+k)*v` with nothing regenerating it.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

N = 128
DU, DV, F, K = 0.16, 0.08, 0.037, 0.06
DT = 1.0
STEPS = 8000
DOMAIN_THRESHOLD = 0.2


def laplacian(f):
    """Periodic 5-point Laplacian on a 2D array, grid spacing dx=1."""
    return (
        np.roll(f, 1, axis=0) + np.roll(f, -1, axis=0)
        + np.roll(f, 1, axis=1) + np.roll(f, -1, axis=1)
        - 4.0 * f
    )


def gs_step(u, v, Du, Dv, F, k, dt=DT, react=True):
    """One explicit-Euler Gray-Scott update step. Returns (u_new, v_new).

    `react=False` is the reaction-off knockout: it drops the `u*v**2`
    autocatalysis term from BOTH equations (no production/consumption
    coupling between species at all), leaving pure diffusion plus the
    feed/removal terms.
    """
    uvv = u * v * v if react else 0.0
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


def run_gs(u0, v0, Du, Dv, F, k, steps, dt=DT, react=True):
    """Advance (u0, v0) `steps` explicit-Euler steps. Returns final (u, v)."""
    u, v = u0.copy(), v0.copy()
    for _ in range(steps):
        u, v = gs_step(u, v, Du, Dv, F, k, dt=dt, react=react)
        assert np.all(np.isfinite(u)) and np.all(np.isfinite(v))
    return u, v


def v_var(v):
    return float(np.asarray(v).var())


def n_domains(v, thr=DOMAIN_THRESHOLD):
    _labeled, count = ndimage.label(np.asarray(v) > thr)
    return int(count)


def test_differential_diffusion_forms_turing_pattern():
    # CFL sanity: explicit 2D diffusion needs Du*dt*4 < 1.
    assert DU * DT * 4 < 1.0

    u0, v0 = seed_uv(seed=1)
    var0 = v_var(v0)
    assert var0 < 0.01  # near-uniform start (observed ~0.0026)

    u, v = run_gs(u0, v0, DU, DV, F, K, STEPS, react=True)
    var_end = v_var(v)
    domains = n_domains(v)

    # Loose floor well above the seed's ~0.003 and well below the observed
    # ~0.0117 (API map) -- a real, unambiguous pattern, not seed noise.
    assert var_end > 0.005
    assert domains > 1  # more than one spot -- a genuine spatial pattern


def test_equal_diffusion_control_stays_uniform():
    # Load-bearing causal control: chemistry fully ON, ONLY the differential
    # diffusion is removed (Du == Dv). This isolates diffusion-driven
    # instability -- the actual Turing mechanism -- as the cause of the
    # pattern above: no differential diffusion -> no Turing instability ->
    # the seed noise damps out instead of amplifying.
    u0, v0 = seed_uv(seed=1)
    Du_eq = Dv_eq = 0.12

    u, v = run_gs(u0, v0, Du_eq, Dv_eq, F, K, STEPS, react=True)
    var_end = v_var(v)
    domains = n_domains(v)

    assert var_end < 1e-4  # ~0.0 (API map: exactly 0.0)
    assert domains == 0


def test_reaction_off_control_stays_uniform():
    # Secondary cross-check: keep the differential diffusion (Du != Dv) but
    # drop the u*v**2 autocatalysis term entirely. With nothing regenerating
    # v, it just relaxes toward 0 under the removal term -- no reaction, no
    # pattern, regardless of the diffusion asymmetry.
    u0, v0 = seed_uv(seed=1)

    u, v = run_gs(u0, v0, DU, DV, F, K, STEPS, react=False)
    var_end = v_var(v)

    assert var_end < 1e-4  # ~0.0 (API map: exactly 0.0)


def test_pattern_vs_controls_contrast_is_unambiguous():
    # The contrast IS the demonstration: patterned v_var >> both controls'
    # v_var, from the identical deterministic seed.
    u0, v0 = seed_uv(seed=1)

    u_pat, v_pat = run_gs(u0, v0, DU, DV, F, K, STEPS, react=True)
    u_eq, v_eq = run_gs(u0, v0, 0.12, 0.12, F, K, STEPS, react=True)
    u_off, v_off = run_gs(u0, v0, DU, DV, F, K, STEPS, react=False)

    var_pat = v_var(v_pat)
    var_eq = v_var(v_eq)
    var_off = v_var(v_off)

    assert var_pat > 0.005
    assert var_eq < 1e-4
    assert var_off < 1e-4
    # Orders of magnitude apart -- an unambiguous separation.
    assert var_pat > 50 * max(var_eq, var_off, 1e-9)
