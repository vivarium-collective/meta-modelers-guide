# Code-verified API map — study 7 `autopoiesis` (Fig 9, §"Self-organized processes")

Investigation: `the-cellular-interface-multicellular`. Worktree: `<worktree>` (aka
`~/code/meta-modelers-guide--cpm-multicellular`). Interpreter: the repo `.venv`'s
python with `PYTHONPATH=<worktree>` prepended. Every number below comes from a real
run of a prototype (`scratchpad/protocell.py`) built directly on the shipped
`meta_modelers_guide/condensate/cahn_hilliard.py` field-process template — not from
reasoning about the code.

## 1. Summary + recommendation

**Recommended realization (one line):** Option (a) — a **pure-numpy reaction-diffusion
protocell**: a scalar membrane-density field `phi` on a periodic grid under
`dphi/dt = D·lap(phi) − k_decay·phi + production`, where `production` (the "internal
metabolism") fires **only where the membrane still topologically encloses an interior**
and is deposited back onto the existing membrane — so closure is literal, and the
negative control is the single-variable knockout `k_prod = 0`. This is cleaner and more
honestly *autopoietic* than the CPM option (b): the persistence is provably **caused by
the internal loop** (Q4 knockout) and gated on the boundary staying intact (Q3 viability
bound), not a bistable pattern that happens to be stable. Option (b) is not needed and
adds a heavy `cpm` dependency for no extra closure content (see Q1).

**Confirmed persist-vs-decay contrast** (canonical regime `D=0.02, k_decay=0.01,
k_prod=0.03`, 64×64 grid, Gaussian-annulus seed, boundary-integrity metric = enclosed
interior area in pixels; run to 3000 steps):

| Arm | metric t=0 | t=1000 | t=2000 | t=3000 | outcome |
|---|---|---|---|---|---|
| **Closed loop** (`k_prod=0.03`) | enclosed **556**, mass 859 | 292, 901 | 276, 828 | **enclosed 276, mass 831** | **PERSISTS** (plateau/homeostasis) |
| **Negative control** (`k_prod=0`) | enclosed **556**, mass 842 | 0, 0 | 0, 0 | **enclosed 0, mass 0** | **COLLAPSES**, time-to-collapse **step 101** |

The knockout is load-bearing and unambiguous: the *only* difference is `k_prod`, and it
flips enclosed-area from a stable 276 to 0. Multi-seed (5 noisy seeds): closed loop ends
enclosed ∈ **[292, 294]** (all > 0), control ends **0 on every seed** (Q7).

---

## 2. Verified API — the 7 questions

All snippets import from the prototype `scratchpad/protocell.py` (a faithful,
`cahn_hilliard.py`-shaped realization: periodic 5-point `lap()`, an explicit per-step
update, `scipy.ndimage.binary_fill_holes`/`label` for the closure detector). Run with
`PYTHONPATH=<worktree>` and the repo `.venv` python.

### Q1 — Cleanest runnable realization: (a) reaction-diffusion protocell. PROVEN.

Both arms were run from the identical seed; the sweep below shows the contrast is robust
across the whole regime box, not a single tuned point:

```
# from a parameter sweep, run to 3000 steps, both arms from the same seed
D=0.02 kdec=0.01 kprod=0.030 | CLOSED end enclosed= 276 mass=  831.3 | CTRL end enclosed=  0 mass=0.0
D=0.02 kdec=0.01 kprod=0.050 | CLOSED end enclosed= 164 mass=  844.8 | CTRL end enclosed=  0 mass=0.0
D=0.01 kdec=0.01 kprod=0.030 | CLOSED end enclosed= 276 mass=  842.1 | CTRL end enclosed=  0 mass=0.0
D=0.01 kdec=0.005 kprod=0.030| CLOSED end enclosed= 164 mass=  993.9 | CTRL end enclosed=  0 mass=0.0
```

In every cell of the box the closed loop keeps enclosed-area > 0 and mass near its seed
value, while the control decays to exactly 0. The persistence is **self-limiting**
(homeostatic), not runaway: production is deposited proportional to `phi` and scaled by
the enclosed area, so as the membrane thickens inward the interior shrinks, throttling
production until it balances decay — the trajectory plateaus (556→292→276) rather than
growing without bound. That self-regulation is the autopoietic signature, and it falls
out of the closure coupling, not a hand-tuned setpoint.

Option (b) (CPM `set_target_volume` resorption) was **not** built: the shipped
`cpm/disintegration.py` already proves a CPM cell's boundary can be driven down via
`world.set_target_volume(cid, target)` (decay direction) and that connectivity /
`lambda_volume` / `temperature` are **not** runtime levers (its module docstring, "NOT
usable as runtime fragmentation levers... verified no-op / init-only"). So (b) can do the
decay arm, but the *closure* arm would need an internal "surface-maintenance" term that
CPM exposes no clean runtime setter for, and it drags in the heavy `cpm`/Rust world for
no closure content that (a) doesn't demonstrate more directly. Recommend (a).

### Q2 — Boundary-integrity / persistence metric. DEFINED + COMPUTED for both arms.

**Metric: enclosed interior area** = `binary_fill_holes(phi > thr) & ~(phi > thr)`
summed (pixels). It is the right separator because it is **topological**: a ring encloses
its center (area > 0); a ring with any gap leaks to the border and `fill_holes` returns
the membrane only (area = 0). It cleanly reads "there is still a bounded inside" vs "the
boundary is gone." Secondary readouts: total membrane mass `sum(phi)` and `max(phi)`.

Full trajectory (canonical regime), both arms, recorded every 500 steps:

```
CLOSED  : t0:A=556,m=859 | t500:A=332,m=1028 | t1000:A=292,m=901 | t1500:A=276,m=842 | t2000:A=276,m=828 | t2999:A=276,m=831   persists=YES  time_to_collapse=None
CONTROL : t0:A=556,m=842 | t500:A=0,m=6      | t1000:A=0,m=0     | t1500:A=0,m=0     | t2000:A=0,m=0     | t2999:A=0,m=0       persists=NO   time_to_collapse=101
```

The metric holds a flat plateau for the closed loop and drops to 0 within ~100 steps for
the control — an order-of-magnitude-clean separation with no overlap.

### Q3 — The closure loop, concretely (why it is autopoietic, not just stable). VERIFIED.

The minimal coupling: **production depends on the boundary still enclosing an interior.**
`production` is non-zero only when `enclosed_interior(phi).sum() >= A_min` (i.e. the
membrane is topologically closed), and the produced material is deposited *onto existing
membrane* (`prop to phi`), never ex nihilo. So the internal process's ability to make
boundary material is conditioned on the boundary it maintains — a closed loop, not an
external supply.

**Viability bound (beer2023 "constraints on the shared state that must be maintained")** —
verified by breaking the boundary at steady state and watching it fail to recover:

```
steady state: enclosed=276 mass=842
cut  20deg wedge -> enclosed right after cut=   0 ; after 1500 steps enclosed=0 mass=0  (DIED)
cut  60deg wedge -> enclosed right after cut=   0 ; after 1500 steps enclosed=0 mass=0  (DIED)
cut 120deg wedge -> enclosed right after cut=   0 ; after 1500 steps enclosed=0 mass=0  (DIED)
```

Puncturing the membrane opens the interior to the exterior → enclosed-area = 0 → the
metabolism (a global function of closure) shuts off → the whole structure relaxes to
`phi = 0` under decay+diffusion. A broken boundary **cannot repair itself from nothing** —
exactly the viability bound. This also realizes the disintegration cascade quote (paper
§Disintegration): "the system transitions from an actively maintained, far-from-equilibrium
state to one dominated by diffusion, equilibration."

**Honest nuance (a plan decision, not a defect):** closure here is *global and binary* —
the metabolism runs only if the cell as a whole is intact, so any topological breach is
fatal and there is no graded puncture threshold and no self-healing of holes. The loop
maintains an already-intact boundary against distributed decay; it does not patch a gap.
A *local* production variant (deposit near interior-adjacent membrane so diffusion can
bridge a small gap before the interior fully leaks) would give a graded viability bound
with repair — see Q1 open decisions.

### Q4 — Negative-control design: the single-variable knockout. VERIFIED.

`k_prod = 0` — production off — turns the closed loop into a mere vesicle (a boundary
with no internal maintenance). Everything else (seed, `D`, `k_decay`, grid, steps) is
byte-identical. Result: enclosed-area 556 → 0 by step 101, mass → 0 (the CONTROL rows
throughout). This is the study's load-bearing control and it is a clean one-line flip.
(A *second*, sharper knockout also exists and is verified in Q3: keep `k_prod=0.03` but
break closure by puncture — same collapse, isolating the *closure* rather than the
*production rate* as the necessary condition.)

### Q5 — Framework + deps. CONFIRMED pure-numpy (+ scipy.ndimage). No cpm/cobra/spatio_flux.

The physics is `numpy` only (periodic `lap` via `np.roll`, exactly `cahn_hilliard.py`'s
`laplacian`). The closure detector needs `scipy.ndimage.binary_fill_holes` and
`.label` — `scipy` is already imported **unguarded** at module top of the shipped
`cpm/disintegration.py`, so the study sits on identical footing (it is present in the
env; `disintegration.py` relies on it the same way). No `cobra`, no `cpm`, no
`spatio_flux`, no CPM world.

**importorskip guards the tests will need:** the pure-numpy/scipy physics test needs
**none** (numpy+scipy are core, always present — matching `tests/test_cahn_hilliard.py`,
whose physics test has no guard). Only a composite-registration/`Composite`-level test
needs `pytest.importorskip("process_bigraph")` — exactly the one guard
`test_cahn_hilliard.py` uses at its composite test (line 68). No cobra/cpm guard.

### Q6 — Observables + honest scope. SPECIFIED.

Emit per tick (all **absolute readings**, so `overwrite[...]` on the process outputs —
same reasoning as `CahnHilliard`'s `phi_var`/`phi_mean` being `overwrite[float]`):
`enclosed_area` (the integrity metric), `membrane_mass` (`sum(phi)`), `phi_max`, a
boolean `persists`/`collapsed` flag (`enclosed_area > 0`), and `released_tick`-style
`time_to_collapse` (first tick enclosed-area hits 0; 101 for the control, `None`/−1 for
the closed loop). The `fields` store carries the real `phi` **delta** (see Q7). Run both
arms; the finding IS the contrast (persists vs collapses).

**Honest scope — what is / isn't demonstrated.** Demonstrated: *closure* — a minimal
self-maintaining boundary whose persistence is **caused** by an internal process that is
itself gated on the boundary, provable by the `k_prod=0` knockout and the puncture
viability bound. **Not** demonstrated: any real membrane chemistry, real metabolism,
molecular components, or a molecularly-detailed protocell. `phi` is an abstract
membrane-density field; "production" is a lumped rate, not a reaction network. This is a
toy autopoiesis (the Maturana–Varela / paper closure *pattern*), matching the plan's own
caveat ("illustrates the closure pattern, not validated autopoiesis";
`docs/superpowers/plans/2026-08-20-paper-aligned-studies.md` Task 9).

### Q7 — Gotchas. VERIFIED.

- **Numerical stability is MILD, unlike CahnHilliard.** This is a *second-order*
  reaction-diffusion (Allen-Cahn-like, non-conservative) scheme, not the *fourth-order*
  biharmonic Cahn-Hilliard, so it obeys the ordinary explicit-diffusion CFL, not the stiff
  `dt < dx^4/(16 M kappa)` limit. Measured: `D=0.02..0.24` stay finite and bounded;
  `D=0.26` begins to blow up (`max_phi`→8.2), `D=0.30`→1.7e31, `D=0.50`→1e140. The limit is
  the classic 2D `D <= 0.25` (dx=1). Canonical `D=0.02` is comfortably inside it — no
  pinned-stiff-dt fragility to carry. Guard analogously to CahnHilliard: raise loudly on a
  non-finite `phi` rather than emitting NaN silently.
- **Non-conservative, on purpose.** Unlike CahnHilliard (mass-conserved), membrane mass is
  *produced and decays*, so do NOT assert mass conservation — assert the persist-vs-decay
  *contrast* instead. Mass being held near its seed value in the closed loop
  (~831 vs seed ~850) is homeostasis, not a conservation law.
- **Field-write delta convention — reuse CahnHilliard's exactly.** The process must read
  the current `phi` from the additive `fields` store, advance a local copy, and emit
  `phi_new − phi_read` (NOT the full field, which the engine would sum onto the old one and
  double it). Verified against the engine's additive apply: summing the emitted deltas over
  50 ticks reproduces `phi_new` exactly (`store == phi_new: True`).
- **Reproducibility.** The seed is a deterministic Gaussian annulus (no RNG needed for the
  headline run); the optional noisy multi-seed uses `np.random.default_rng(seed)`
  (never time/uuid), matching `test_cahn_hilliard.py::_seed_phi`. The persist/collapse
  contrast is identical across all 5 seeds (enclosed ∈ [292,294] closed, 0 control).
- **Threshold coupling.** The integrity metric depends on `thr` (0.30) relative to the
  membrane amplitude and on `D` not thinning `phi` below `thr` before steady state. Within
  the swept box the closed loop always stays above threshold; a much larger `D` (near the
  0.25 CFL) thins the membrane and can extinguish closure on its own — keep `D` small.

---

## 3. Carried-over constraints (the hardened-pipeline conventions this study must follow)

- **Cite the paper by section title + quoted phrase, not figure number alone**
  (`deferrals.md` / review D-2). Home section: **§"Self-organized processes"** (Fig 9,
  figure file `self_organized_process.pdf`). The pass/fail criterion to quote verbatim:
  *"A membrane alone is insufficient: a vesicle may form a boundary without constituting a
  living system. A stronger criterion is that the processes inside the boundary
  collectively contribute to maintaining the organization that, in turn, keeps those
  processes possible."* And the viability-bound line (beer2023): *"viability bounds arise
  as constraints on the shared state that must be maintained for the composition to
  persist."* The negative-control vesicle **is** the "membrane alone"; the closed loop is
  the "stronger criterion." Re-verify these against the current paper source at
  study-accept time.
- **Multi-seed robustness** (`deferrals.md` "Not deferred"; the convention established in
  `tests/test_cellcell_multiseed.py`): the run is deterministic for the clean annulus seed,
  but if any noise is added, sweep ≥5 seeds and report the range beside the headline
  (verified here: closed enclosed ∈ [292,294], control ≡ 0). Assert the *qualitative* claim
  (closed persists, control collapses) per seed.
- **Honest scope paragraph** (review E-11 / units-and-timescales): name the toy-real
  boundary — closure pattern demonstrated, molecular protocell NOT — in `question` /
  `biological_summary` / a limitation, biology-first voice (lead with the vesicle-vs-living
  distinction, demote the plumbing to one sentence), as
  `biomolecular-complementarity-spatial/study.yaml` does for its own interface-work gap.
- **Constants ledger + units sheet** (`constants-ledger.md`, `units-and-timescales.md`):
  add a row for this study — no metabolism/cobra (like disintegration and the condensate),
  regime `D=0.02, k_decay=0.01, k_prod=0.03, thr=0.30, 64×64, ~3000 steps`. Steps are
  **model time** (dimensionless relaxation), `phi` is dimensionless membrane density, grid
  pixels have no assigned micron size — state it, matching the units sheet's convention.
- **Control taxonomy** (review D-6): label the `k_prod=0` arm `control: negative`
  correctly (it is a genuine single-variable knockout that abolishes the effect), unlike
  the mislabeled structural checks the review flagged.

---

## 4. Open risks / decisions for the plan

1. **Closure is global + binary (no self-repair).** The verified viability bound is
   all-or-nothing: any topological breach is instantly fatal (Q3). This is clean and
   defensible ("a breached cell has no functioning metabolism"), but it means the study
   shows *maintenance against distributed decay*, not *puncture healing*. **Decision:** ship
   the crisp global version (recommended — it maps directly to the paper's binary
   living/not-living distinction), OR build the *local-production* variant (deposit near
   interior-adjacent membrane so diffusion bridges a small gap) to get a graded viability
   threshold with repair. The latter is a second mechanism; scope it as a follow-up unless
   graded repair is explicitly wanted.
2. **The metric must be gated like the sorting study's cohesion guard.** Enclosed-area = 0
   can mean either "dissolved" (mass→0, the real collapse) or, hypothetically, "membrane
   thickened until it filled its own interior" (mass high, area 0). The latter did NOT occur
   in any run (closed loop plateaus at area 276 > 0), but the pass/fail should read
   enclosed-area **together with** membrane mass — persists := `enclosed_area > 0 AND mass
   held near seed` — so a filled-in blob can never be misread as a persisting vesicle. Same
   load-bearing-guard pattern as `biomolecular-complementarity`'s hetero_frac + cohesion.
3. **`thr`/`D` sensitivity.** The integrity metric depends on the threshold and on `D`
   staying well below the 0.25 CFL (a large `D` thins the membrane below `thr` and
   extinguishes closure on its own — a confound with the `k_prod` knockout). Pin `D` small
   and document `thr`; ideally show the knockout contrast at ≥2 thresholds so the finding
   is not threshold-fragile. This is the single most likely reviewer objection.

*Prototype for every number above:* `scratchpad/protocell.py` (not committed; a scratch
realization of the `cahn_hilliard.py` template). Where a claim is unverified it is marked
so; everything in §1–2 is from a real run.
