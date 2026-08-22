# Code-verified API map — study 5 `molecular-interfaces` (Fig 7, §"Molecular interface")

Investigation: `the-cellular-interface-multicellular`. Worktree: `<worktree>` (aka
`~/code/meta-modelers-guide--cpm-multicellular`). Interpreter: the repo `.venv`'s python
with `PYTHONPATH=<worktree>` prepended. Every number below comes from a real run of a
prototype (`scratchpad/gs_probe.py`, `gs_probe2.py`, `gs_engine.py`) built directly on the
shipped `meta_modelers_guide/condensate/cahn_hilliard.py` field-process template — not from
reasoning about the code. This study is the **spatial analogue** of the completed
specification-stage study `draft-to-living-cell/molecular-interfaces`
(`workspace/studies/molecular-interfaces/study.yaml`), which compiled one molecular
mechanism (F1Fo ATP synthase) behind the Fig 7 four-channel interface as a coupled-flux
transducer. Where that study made **one molecule's four channels** executable at a point,
this one makes the **chemical channel spatial**: local molecular reactions + diffusion
producing emergent spatial structure (Turing patterning).

## 1. Summary + recommendation

**Recommended realization (one line):** a **pure-numpy two-species Gray-Scott
reaction-diffusion process** (`GrayScott`, a new `meta_modelers_guide/molecular/` field
process mirroring `CahnHilliard`), where local autocatalytic chemistry `U + 2V → 3V`,
`V → P` plus differential diffusion turns a near-uniform noisy seed into an emergent
**Turing spot pattern** — "the chemical molecular channel made spatial" — with the
**pattern-formation metric = spatial variance of V** (seed-robust) plus a domain count
(seed-sensitive, reported as a range).

**Four-channel decision: chemical + a verified second (thermal) channel.** Realize the
chemical channel spatially as the primary result, and add ONE cheap, genuinely-coupled
**thermal** channel — a temperature field modulating the reaction rate by an Arrhenius
factor `rate(T) = exp(−Ea·(1/T − 1/Tref))`. Verified below: temperature *grades* the
pattern (fewer/coarser spots as T rises), so it is a real second modality, not decoration.
The **electrostatic and mechanical** channels stay named as the investigation's already-
stated four-modality gap. **Consistency caveat (Q3 / Open risk #1):** the investigation's
`what_this_does_not_demonstrate` currently asserts "Every study here realizes ONLY the
chemical port"; adding thermal here makes that sentence false, so the plan MUST update that
block to carve study 5 out as the study that adds a thermal channel (electrostatic +
mechanical remain the gap). If the plan prefers zero edits to shared honesty prose,
fall back to chemical-only and name all three non-chemical channels as the gap — the
chemical result stands on its own.

**Confirmed pattern-vs-uniform contrast** (canonical regime `Du=0.16, Dv=0.08, F=0.037,
k=0.06`, 128×128 periodic grid, near-uniform seed = `u≈1, v≈0` + 2% noise + a few
nucleation patches, deterministic RNG seed 1, dt=1.0, metric = `v.var()`; run to 8000
steps):

| Arm | v_var t=0 | t=2000 | t=8000 | n_domains t=8000 | outcome |
|---|---|---|---|---|---|
| **Reaction on** (`Du≠Dv`) | 0.00257 | 0.01191 | **0.01165** | 11 | **PATTERNED** (Turing spots) |
| **Equal-diffusion control** (`Du=Dv=0.12`, reaction ON) | 0.00257 | — | **0.0** | 0 | **UNIFORM** (Turing instability suppressed) |
| **Reaction-off control** (`U·V²` term knocked out) | 0.00257 | — | **0.0** | 0 | **UNIFORM** (relaxes to `v≈0`) |

Both controls drive the metric to **exactly 0.0**. The **equal-diffusion knockout is the
load-bearing causal control** (recommended primary): it leaves the chemistry fully ON and
removes only the differential diffusion, isolating *diffusion-driven instability* — the
actual Turing mechanism — as the cause of structure. The reaction-off knockout is a simpler
secondary cross-check. Multi-seed (seeds 1–5): `v_var ∈ [0.01163, 0.01191]` (tight,
seed-robust); `n_domains ∈ [10, 19]` (seed-sensitive → report as a range, not a golden
value; Q7).

---

## 2. Verified API — the 7 questions

All snippets import from `scratchpad/gs_probe.py` (a faithful pure-numpy prototype: periodic
5-point `laplacian` and `gs_step` copied in shape from `cahn_hilliard.py`).

### Q1. Cleanest runnable realization (+ a run that proves it)

**Gray-Scott, pure numpy.** Two coupled species on a periodic grid, explicit Euler, dx=1:

```
du/dt = Du·lap(u) − rate·u·v² + F·(1−u)      # U replenished (feed F), consumed by reaction
dv/dt = Dv·lap(v) + rate·u·v² − (F+k)·v       # V autocatalytically produced, removed (F+k)
```

This is a minimal **enzymatic/autocatalytic network** (`U + 2V → 3V`, `V → P`): V catalyzes
its own production from U — the chemical molecular channel — and `Dv < Du` (inhibitor
diffuses slower) gives the Turing instability. Run (`scratchpad/gs_probe.py`, engine of
record for the numbers above):

```
--- PATTERN (react=True, F=0.037 k=0.060) ---
{'v_var': 0.01165, 'v_var0': 0.00257, 'n_domains': 11, 'v_max': 0.372, 'finite': True}
--- NEGATIVE CONTROL (react=False) ---
{'v_var': 0.0, 'v_var0': 0.00257, 'n_domains': 0, 'v_max': 2.5e-323, 'finite': True}
--- alt regime F=0.055 k=0.062 ---
{'v_var': 0.01629, 'v_var0': 0.00257, 'n_domains': 14, ...}
```

Both `F=0.037,k=0.06` (spots) and `F=0.055,k=0.062` give a clean legible pattern; **use
`F=0.037,k=0.06`** (the classic spot regime) as canonical.

**Why not reuse an existing process.** Verified by reading the code: `spatio_flux` ships
`DiffusionAdvection` (`spatio_flux/processes/diffusion_advection.py` — pure diffusion +
advection on one field, *no reaction coupling*, cannot Turing-pattern) and `MonodKinetics`
(`monod_kinetics.py` — well-mixed reaction rates, *not spatial*). Neither is a two-species
spatial RD system, so composing them would be more code than the ~15-line `gs_step`.
`viva-cpm` exposes an **SBML subcellular path** (`cpm.subcellular.sbml.SBMLSubcell`, extra
`pbg-cpm[sbml]` → `libroadrunner`/`tellurium`/`pbg-tellurium`; `viva-cpm/pyproject.toml:35`,
`README.md:62`) — a real per-cell ODE reactor, but it is **well-mixed per cell, not a
spatial reaction-diffusion field**, and pulls a heavy optional dependency. It does not give
emergent *spatial* structure, so it is the wrong tool for "the chemical channel made
spatial." **Recommendation: build the pure-numpy `GrayScott`; cite the cpm SBML path in
prose as the (heavier, non-spatial) alternative the paper's "cpm SBML subcellular" phrase
gestures at.**

### Q2. The demonstrating metric (+ negative control at ~0)

**Primary metric: `v_var = v.var()`** — spatial variance of the inhibitor field. Seed-robust
(see Q7) and cleanly separates patterned from uniform. **Secondary: `n_domains`** =
`scipy.ndimage.label(v > 0.25)[1]`, the count of connected concentration domains (spots).
Time series of the metric *rising* from the near-uniform seed (`scratchpad/gs_probe2.py`):

```
=== time series, pattern (F=.037,k=.06) ===  (step, v_var, n_domains)
[(0, 0.00257, 0), (2000, 0.01191, 17), (4000, 0.01174, 11), (6000, 0.01164, 10), (8000, 0.01165, 11)]
```

`v_var` rises ~4.5× from the seed (0.00257 → 0.0117) and plateaus; domains coarsen from 17
to ~11 as spots merge. **Negative controls both hold at exactly 0.0** (see the table in §1;
`gs_probe2.py`): equal-diffusion (`Du=Dv=0.12`, reaction ON) → `v_var=0.0, n_domains=0`;
reaction-off → `v_var=0.0`. The contrast IS the demonstration, mirroring the other studies'
knockouts.

### Q3. The four molecular channels — honest scope (thermal verified)

Chemical is realized spatially (above). **Thermal is a real, verified second channel**: an
Arrhenius factor on the reaction rate, `rate(T)=exp(−Ea·(1/T−1/Tref))`, `Tref=1.0` (reduced
units — no physical calibration). With a gentle `Ea=0.6`, temperature *grades* the pattern
(`scratchpad/gs_probe2.py`):

```
=== THERMAL channel (gentle Arrhenius Ea=0.6) ===
  T=0.92: rate=0.949 -> v_var,n_dom = 0.01418, 55   (cooler: finer, many spots)
  T=1.00: rate=1.000 -> v_var,n_dom = 0.01165, 11   (reference)
  T=1.08: rate=1.045 -> v_var,n_dom = 0.00662,  1   (warmer: pattern washing out)
```

`v_var` moves monotonically with T (0.0142 → 0.0117 → 0.0066) and the domain count collapses
55 → 11 → 1: temperature genuinely tunes whether/how the pattern forms — a second molecular
channel coupled to the chemistry. (Note: a *steep* `Ea=2.0` makes it an on/off cliff — only
T≈1.0 patterns; use the gentle `Ea` for a legible graded demo.) **Electrostatic and
mechanical are NOT realized** — named as the four-modality gap (see the consistency caveat
in §1 and Carried-over constraints below).

### Q4. Databases-as-partial-specifications hook (framing + a cheap gesture)

**Recommendation: (a) frame in prose + a lightweight typed-port annotation — not a live DB
import.** The paper's original claim (PDB/Reactome/ChEBI/GO as *partial* specifications of
molecular interfaces and their types) is a framing hook. Realize it cheaply and honestly by
naming the abstract Gray-Scott reaction as a concrete typed scheme and annotating the
`GrayScott` species ports with the identifier each database *would* supply, making the
"partial" point literal: **ChEBI** names the species (U, V, P as `chebi:…`), **Reactome**
names the reaction topology (`U + 2V → 3V`), **PDB** would give the catalyst's 3D structure
(absent here — the toy has no conformation), **GO** would give the molecular function. No
runtime DB dependency; the annotation lives in config/comments and the study prose. This is
the review §A5 hook ("map a Reactome pathway fragment onto typed process ports") at its
cheapest honest form. A live Reactome/ChEBI fetch is explicitly out of scope (adds a network
dependency for a framing gesture).

### Q5. Framework + deps

**Pure numpy + `scipy.ndimage` (for `label`), no `cpm`/`cobra`/`spatio_flux`** — exactly
like `CahnHilliard`/`Protocell`. Verified importable in the repo `.venv`: `numpy 2.5.2`,
`scipy` (`scipy.ndimage`), `process_bigraph` all present. Guard convention: tests
`pytest.importorskip("process_bigraph")` for the engine-run test (matching
`tests/test_cahn_hilliard.py`); the pure-physics tests need only numpy/scipy. Do **not**
add the `pbg-cpm[sbml]` extra.

### Q6. Observables + honest scope

Emit, mirroring `CahnHilliard`'s `overwrite[...]` scalars: `v_var` (pattern-formation
metric), `n_domains`, per-species field stats (`v_mean`, `v_max`), and a `patterned` flag
(e.g. `v_var > 0.005`). The `fields` map[array] store carries **two** species (`u`, `v`),
each written as a **delta** (see Q7). **Honest scope:** this is a TOY reaction-diffusion
demonstration of the *chemical* molecular channel producing *spatial structure* (Turing
patterning) + a coupled *thermal* channel — it is NOT real molecular structure/conformation
(PDB-level: the toy species have no position/orientation/conformation beyond a grid
concentration), NOT the electrostatic or mechanical channels, and NOT a specific named
pathway's kinetics. Parameters are toy-real (tuned for a legible pattern), not fitted; cite
alongside `docs/superpowers/units-and-timescales.md` (dimensionally self-consistent within a
run, not SI).

### Q7. Gotchas (all verified)

- **CFL / numerical stability.** Explicit 2D diffusion needs `Du·dt·4 < 1`. At `Du=0.16,
  dt=1.0` → `0.64 < 1` ✓ (printed by `gs_probe.py`). Guard at construction like `Protocell`
  (raise on violation) and re-check finiteness each tick like `CahnHilliard`.
- **Seed sensitivity → multi-seed convention REQUIRED.** Unlike deterministic `Protocell`,
  the Gray-Scott seed noise IS stochastic. `v_var` is seed-robust (`[0.01163, 0.01191]`
  across seeds 1–5) but `n_domains` swings `[10, 19]`. **Use `v_var` as the pass/fail metric
  with a loose floor (e.g. `> 0.005`), report `n_domains` only as a range** — do not pin a
  golden domain count. This matches the investigation's CPM/Metropolis multi-seed convention
  (contrast autopoiesis, whose degenerate single-point range came from having no RNG).
- **Delta-write with TWO fields — verified through the real engine.**
  `scratchpad/gs_engine.py` registers a minimal `GrayScott` `Process` on `build_core()` and
  runs it 8 ticks through `Composite`; the store must end holding `v` (not `v` doubled)
  because the engine SUMS emitted arrays. Output:

  ```
  delta-write matches reference (no double-count): True
  engine obs v_var: 0.01165  n_domains: 11.0
  reference v_var: 0.01165
  ```

  So `update()` emits `{"fields": {"u": u−u0, "v": v−v0}}` (a delta *per species* in the one
  shared map[array] store) and `overwrite[float]` scalars — the exact `CahnHilliard`/
  `Protocell` convention, extended to two keys. (Registration API note: use
  `core.register_link(name, cls)`, not `register_process`.)
- **Grid size / steps for a legible pattern + GIF.** 128×128, 8000 steps reaches a plateaued
  spot field (metric flat after ~2000 steps). For the engine process use `steps_per_tick`
  ~500–1000 and ~8–16 ticks (matches the 1000×8 used in `gs_engine.py`).

---

## 3. Carried-over constraints (hardened conventions)

- **Field-process template.** New process lives at e.g.
  `meta_modelers_guide/molecular/gray_scott.py`, mirroring `condensate/cahn_hilliard.py`
  exactly: module-level `laplacian`/`gs_step`, `_f` default helper, `grid` as `map[integer]`
  with **no `_default`** (the bigraph-schema map-merge trap documented in
  `cahn_hilliard.py`/`sorting.py`), `fields: map[array]` in/out, `overwrite[...]` scalar
  observables, delta-write, construction-time CFL guard + per-tick finiteness guard.
- **Zero-value config restore.** If any negative-control knockout is expressed as a scalar
  config set to `0` (e.g. `rate=0` or `Dv` equalized via a `0` flag), restore caller-passed
  zeros in `__init__` like `Protocell` does — `core.fill` treats `0` as empty and refills the
  default (documented in `autopoiesis.py:166–178`). The recommended equal-diffusion control
  sets `Dv=Du` (a nonzero value) and sidesteps this; the reaction-off control needs the
  restore or a boolean `react` flag.
- **Multi-seed, stochastic.** Report `v_var` across ≥5 seeds; the pattern metric is the
  claim, the domain count is a range. This study IS seed-sensitive (§ Q7) — state it plainly.
- **Honest scope, §-cited.** Frame against paper §"Molecular interface"/Fig 7 and review
  §A5. Chemical channel spatial + thermal coupling demonstrated; electrostatic + mechanical
  named as the four-modality gap (`investigation.yaml → what_this_does_not_demonstrate`,
  `docs/superpowers/deferrals.md` item 6). Toy-real, not fitted; no PDB-level conformation.
- **Four-modality gap consistency (load-bearing).** The investigation honesty block and
  `deferrals.md` item 6 currently say only the chemical port is realized anywhere. This study
  adds thermal — the plan must reconcile that (update the block to name study 5 as the
  thermal-channel exception) or drop thermal. Do not ship the thermal channel while the block
  still claims chemical-only.

## 4. Open risks / decisions for the plan

1. **Thermal-channel consistency edit (highest).** Adding thermal contradicts the
   investigation's standing "only the chemical port" honesty prose and `deferrals.md` item 6.
   Decision: either (a) update `what_this_does_not_demonstrate` + `deferrals.md` to carve
   study 5 out as the study that adds a thermal channel (recommended — it is a genuine
   advance and it's verified), or (b) realize chemical-only and keep the block untouched.
   Either is defensible; do not leave them inconsistent.
2. **Which negative control is primary.** Recommend the **equal-diffusion knockout**
   (`Du=Dv`, chemistry ON) as the load-bearing causal control (isolates the Turing mechanism)
   and reaction-off as a secondary cross-check. Confirm the plan wants both, or picks one.
   Both give `v_var → 0.0` (verified).
3. **Databases hook depth.** Recommend prose + typed-port annotation only (Q4). If a reviewer
   wants an actual Reactome/ChEBI fragment mapped, that is a larger, network-dependent gesture
   — flag it as a deferral rather than silently scoping it in.

Minor: the `patterned` flag threshold (`v_var > 0.005`) is a tuned demonstration cut, not a
principled bound — pick it loosely below the observed 0.0117 and well above the controls' 0.0,
and say so (mirrors the autopoiesis `enclosed_area > 50` loose-floor convention). Domain-count
`> 0.25` threshold on `v` is likewise a tuned cut; report it as such.
