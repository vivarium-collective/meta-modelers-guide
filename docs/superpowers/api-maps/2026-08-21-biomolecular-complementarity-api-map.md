# Code-verified API map — STUDY 6 `biomolecular-complementarity` (spatial)

**Date:** 2026-08-21
**Investigation:** `the-cellular-interface-multicellular`
**Analogue:** Fig 8 selectivity/condensates → **differential-adhesion cell sorting** (Steinberg = complementarity made spatial) + phase separation for condensates.
**Verified against installed code:** `cpm` (`~/code/viva-cpm/cpm/`, Rust `cpm_core`) via `cpm.schema.load_world`. **No cobra, no spatio-flux field used or needed** (see Q4).
**Interpreter:** `~/code/meta-modelers-guide/.venv/bin/python`, `PYTHONPATH=<worktree>` (`~/code/meta-modelers-guide--cpm-multicellular`).
**Naming note:** there is already a *non-spatial* `biomolecular-complementarity` study under `draft-to-living-cell` (Fig 8 nested-hierarchy cascade). This is its **spatial** counterpart; the plan should slug it `biomolecular-complementarity-spatial` to mirror `cell-cell-coupling-spatial` / `disintegration-spatial`.

---

## 1. Summary + recommended process shape

This study is **pure adhesion energetics** — no metabolism. A single CPM `World` seeded with a **mixed, mutually-adjacent checkerboard of two cell types**, given contact energies where heterotypic contact is costly and homotypic contact is favorable, **demixes under Metropolis dynamics**: like cells cluster, the heterotypic interface shrinks. That is Steinberg's Differential Adhesion Hypothesis, made spatial — and it is the runnable analogue of Fig 8's "complementarity/selectivity" (like binds like). It uses **only `cpm`** — strip the flagship's dFBA/field/cobra machinery entirely.

**Recommended process shape (one line):** ONE world-owning process `CpmSorting`, modeled on `colony_field.py` but with the field/dFBA/cobra removed — it owns one CPM world of two interleaved cell types, `step()`s `mcs` per tick, and emits the heterotypic-interface sorting metric + per-cell type/COM/volume; no `fields` input/output, no cobra model.

**Confirmed sorting regime (reproducible, 3 seeds):**

| contact pair | J | role |
|---|---|---|
| `{a:1,b:1}` = `{a:2,b:2}` (homotypic) | **2.0** | favorable — like cells stick |
| `{a:1,b:2}` (heterotypic) | **11.0** | costly — unlike cells repel |
| `{a:0,b:1}` = `{a:0,b:2}` (medium) | **8.0** | intermediate — clump stays cohesive |

**temperature = 10.0**, `neighbor_order = 2`, `lambda_volume = 2.0`, `target_volume = 25.0`, 64 cells (8×8 checkerboard of 5×5 px), 70×70 lattice, `mcs = 10`/tick, ~600 MCS total.

**Metric (heterotypic interface fraction) t0 → t_end:** **1.000 → 0.116** (seed 1), **0.136** (seed 2), **0.152** (seed 3) — clean, reproducible demixing. Sorting condition holds: J(1,2)=11 > ½(J(1,1)+J(2,2))=2.

Every claim below is backed by a snippet that was actually run (scratch scripts in the session scratchpad: `sort.py`).

---

## 2. Verified API

### Q1 — Sorting dynamics (the crux): mixed clump demixes

Seed the checkerboard (Q3), set the J matrix above, `T=10`, run 600 MCS in `mcs=10` chunks, measure the heterotypic-interface fraction (Q2) each chunk. Real output:

```
=== A demix  J={m1:8,m2:8,11:2,22:2,12:11} T=10 cells=64 tv=25 ===
n_cells=64  layout types 1/2 = 32/32
  MCS    0: hetero_edges=  560 total_intercell=  560 hetero_frac=1.000
  MCS  100: hetero_edges=  236 total_intercell=  905 hetero_frac=0.261
  MCS  200: hetero_edges=  171 total_intercell=  928 hetero_frac=0.184
  MCS  300: hetero_edges=  145 total_intercell=  964 hetero_frac=0.150
  MCS  400: hetero_edges=  117 total_intercell=  984 hetero_frac=0.119
  MCS  500: hetero_edges=  111 total_intercell=  971 hetero_frac=0.114
  MCS  600: hetero_edges=  112 total_intercell=  967 hetero_frac=0.116
```

Monotone-ish decrease, plateauing ~0.11–0.12 (residual domain boundaries between the two consolidated regions). `total_intercell` *rises* (560→~970) as cells compact into a solid mass with more cell–cell contact overall — which is exactly why the **fraction**, not the raw hetero-edge count, is the robust metric.

**Regime map (all seeded identically, 600 MCS, only the varied knob changed):**

```
neutral J (all=8)   T=10 : t0 1.000 -> t600 0.611   # NO sorting — J regime is causal
demix J             T=1  : t0 1.000 -> t600 0.536   # FROZEN — too cold to rearrange
demix J             T=10 : t0 1.000 -> t600 0.116   # clean sort (cell_px 1600->1518, cohesive)
demix J             T=100: t0 1.000 -> t600 0.254   # partial; cell_px 1600->1311 (some erosion)
demix J             T=200: t0 1.000 -> t600 0.255   # cells dissolving, cell_px 1600->471
demix J             T=400: t0 1.000 -> t600 0.000   # FALSE sort: cell_px->0, clump vaporized
```

The neutral-J control (all J=8, so heterotypic is *not* costly) stays mixed at 0.611 — proving the demixing is driven by the J regime, not by CPM dynamics per se. `T=10` is the sweet spot: `T=1` freezes the mixed state; `T≥200` boils the cells off into medium. **The `T=400` line is the metric trap** — `hetero_frac=0.000` looks perfectly sorted but the clump has fully dissolved (`total_intercell=0`), so the metric must be read alongside a cohesion guard (total cell pixels; Q2/gotchas).

### Q2 — Sorting metric definition

Heterotypic interface fraction: over all 4-neighbor lattice-edge pairs where **both pixels are distinct cells** (both `id>0`, `id_a != id_b`), the fraction whose **types differ**. Uses `snapshot()` + `cell_types()` only. Exact verified code:

```python
def hetero_metric(w, NX, NY):
    lat = np.array(w.snapshot()).reshape(NY, NX)   # id per pixel; 0 = medium
    types = np.array(w.cell_types())               # list indexed by id; types[lat] -> per-pixel type
    typ = np.where(lat > 0, types[lat], 0)
    hetero = total = 0
    for a, b, ta, tb in [(lat[:, :-1], lat[:, 1:], typ[:, :-1], typ[:, 1:]),   # horizontal
                         (lat[:-1, :], lat[1:, :], typ[:-1, :], typ[1:, :])]:  # vertical
        both = (a > 0) & (b > 0) & (a != b)        # two DIFFERENT cells adjacent
        total += int(both.sum())
        hetero += int((both & (ta != tb)).sum())
    return hetero, total, (hetero / total if total else 0.0)
```

t0 = **1.000** (checkerboard: every cell's 4-neighbors are the opposite type), t_end = **0.116**. Confirmed monotone-ish decreasing under sorting (Q1 trajectory). **Guard:** when the clump dissolves `total==0` → returns 0.0 (false "sorted"); always emit total cell-pixel count beside it and treat metric as valid only while the clump is cohesive.

### Q3 — Initial mixed seeding (high t0)

An interleaved checkerboard of small **non-overlapping, edge-adjacent** `seed_block`s, type `1 if (r+c)%2==0 else 2`. Each block is 5×5 px, blocks abut with no gap so heterotypic neighbors touch at t0:

```python
for r in range(nrows):
  for c in range(ncols):
    typ = 1 if (r + c) % 2 == 0 else 2
    bx0, by0 = x0 + c*cell_px, y0 + r*cell_px
    cells.append({"type": typ, "target_volume": 25.0, "lambda_volume": 2.0,
                  "target_surface": 0.0, "lambda_surface": 0.0,
                  "seed_block": [bx0, by0, 0, bx0+cell_px, by0+cell_px, 1]})  # half-open, z1=1
```

Confirmed t0 `hetero_frac = 1.000` with `total_intercell = 560` (cells genuinely touch across types). **Contrast — spaced seeding gives a FALSE t0:** the same checkerboard with a 3-px gap between blocks yields `hetero_edges=0 total_intercell=0 frac=0.000` (cells don't touch, metric reads "already sorted"). Adjacency at t0 is mandatory.

### Q4 — Process shape → `CpmSorting` (no field, no cobra)

Every run above imported **only** `cpm.schema.load_world` and called `load_world`, `world.step`, `world.snapshot`, `world.cell_types`, `world.cell_coms`, `world.cell_volumes`. **No spatio-flux field, no `add_field`, no cobra `load_model` — none is needed;** the whole study runs on cpm's adhesion Hamiltonian alone. Recommend one world-owning `Process` modeled on `colony_field.py` (`meta_modelers_guide/cpm/colony_field.py`) but **stripped** of `inputs()={fields}`, `outputs()={fields,...}`, the per-cell cobra models, `_fba`, `_clamp_removal`, and all field writeback. Config: `grid`, `cells` (both types, interleaved), `contact` (full 2-type matrix + per-type medium terms), `temperature`, `mcs`. Tick loop:

```
update(state, interval):
    self.world.step(int(self.config["mcs"]))         # one MC sweep block; targets are static (no growth)
    lat = np.array(self.world.snapshot()).reshape(ny, nx)
    types = np.array(self.world.cell_types())
    emit hetero_metric(...), n_cells per type, and per-cell {type, COM, volume}
```

Cell count is constant (no division/growth/removal), so `target_volume` is set once at seed and never updated — the process just steps and observes.

### Q5 — Cahn-Hilliard scope decision

A minimal Cahn-Hilliard phase-field is **cheap and verified working** — ~8 lines of numpy, a scalar field φ on the grid evolving by `∂φ/∂t = M ∇²(φ³ − φ − κ∇²φ)`:

```python
def lap(f): return np.roll(f,1,0)+np.roll(f,-1,0)+np.roll(f,1,1)+np.roll(f,-1,1)-4*f
mu  = phi**3 - phi - kappa*lap(phi)
phi = phi + dt*M*lap(mu)
```

Seeded with near-critical noise (mean 0, ±0.025), 20000 steps at `M=1, κ=0.5, dt=0.002`: **spinodal decomposition** into two domains, `var 0.0002→0.505`, `min/max −1.00/+1.00`, **mass conserved** (`mean −0.0002→−0.0002`). It is a **separate process over a `fields` store** — no cells, no CPM, fully independent of the sorting core.

**Gotcha found:** CH is numerically stiff. `dt=0.05` blew up to NaN (the biharmonic ∇⁴ term has a tight stability limit ~`dt < Δx⁴/(16Mκ)`); `dt=0.002` is stable. Any CH process must document/guard its dt.

**Recommendation:** **cell-sorting core is the study's demonstrated claim; include the minimal CH as a small, clearly-separate second process framed as the diffuse-interface ("condensate") analogue.** It is cheap enough to ship and the spec explicitly pairs them, but it must be scoped honestly (as the sibling non-spatial study scopes its selectivity gap): the two are **independent** demonstrations of complementarity-as-spatial-separation — CPM cell sorting (discrete, adhesion-energy) and CH phase separation (continuous field) — **not one coupled mechanism**, and neither computes a binding affinity. If the plan wants to keep the increment tight, ship the sorting core alone and note CH as a one-process extension; do **not** attempt to couple φ to the CPM cells (out of scope, unverified).

### Q6 — Observables + demonstrating metric

Emit each tick: (1) the **heterotypic-interface fraction** (Q2) — the headline demixing signal, high→low; (2) **total cell-pixel count** (the cohesion guard, so a dissolved clump isn't misread as sorted); (3) **n_cells per type** (constant here — a regression check); (4) **per-cell type / COM (`cell_coms()[cid]`) / volume (`cell_volumes()[cid]`)**. Demonstrating signal: `hetero_frac` **1.000 → 0.116** while cell-pixels stay ~cohesive (1600→1518 at T=10). Optional domain compactness: per type, radius of gyration of its footprint, or largest connected component fraction (shrinks toward 1 as each type coalesces into one domain).

### Q7 — Verified gotchas

- **`cell_types()` is a list indexed by id, index 0 = medium** (verified `len == n_cells+1 == 65`, first entries `[0,1,2,1,2,1]`). `types[lat]` vectorizes id→type. Same list-not-dict / skip-0 rule the cell-cell-coupling map records for `cell_coms()`/`cell_volumes()`.
- **Temperature is the whole ballgame:** `T=1` freezes the mixed state (0.536), `T=10` sorts cleanly (0.116), `T≥200` dissolves cells into medium, `T=400` fully vaporizes them (metric falsely reads 0.000). Stay near `T=10`.
- **J regime must demix *without* dissolving the clump:** homotypic low (2), heterotypic high (11), medium **intermediate (8)** — medium too low and cells scatter into medium; medium too high and the clump can't relax its heterotypic boundary. Neutral J (all equal) does not sort (0.611).
- **Sorting is slow:** hundreds of MCS. ~600 MCS in `mcs=10` chunks gives ~60 frames — good cadence for a watchable GIF (t0 checkerboard → t_end two domains).
- **Seed adjacency is mandatory** (Q3): a spaced checkerboard gives `total_intercell=0`, a false t0=0.000.
- **`seed_block` half-open, `z1=1` for 2D**; blocks must not overlap (carried constraint). Constant cell count — no division/growth/removal in this study.

---

## 3. Carried-over constraints (still binding)

From the flagship Global Constraints and the prior maps (`2026-08-21-cell-cell-coupling-api-map.md`, `-disintegration-api-map.md`):

- **Worktree discipline:** all work in `~/code/meta-modelers-guide--cpm-multicellular`; `PYTHONPATH=<worktree>` prepended; venv interpreter as above.
- **`cell_coms()` / `cell_volumes()` / `cell_types()` are Python lists indexed by id, element [0] = medium.** Iterate ids `1..n_cells`; never `.keys()`/`.get()`.
- **Full import-path process addresses** for any composite (`local:!cpm.processes...`); in-repo processes register via `build_core()`. (This study likely doesn't need the CPMProcess wrapper — it owns a raw `World` like `CpmColonyField` — but if wired as a composite, use the full address.)
- **Shared-grid contract:** arrays `(ny, nx)`; `snapshot()` flat `x + y*nx` → reshape `(ny, nx)`.
- **`seed_block` half-open, `z0,z1 = 0,1` for 2D**; non-overlapping blocks.
- **`overwrite[...]` on absolute per-tick observables** (metric, per-cell type/COM/volume) — plain float/list applies additively/concatenates.
- **`set_contact` accepts `a==b`** (homotypic terms) and the full 2-type matrix incl. `{a:1,b:2}` and per-type medium `{a:0,b:1}`/`{a:0,b:2}` (already probed; re-exercised here).
- **Toy-real + honest framing:** plausible J/T, not a fitted tissue; keep the sibling study's honest voice — this demonstrates **differential-adhesion sorting**, the spatial reading of complementarity, **not** a molecular binding-affinity/selectivity mechanism (no partner-choice term exists, exactly as the non-spatial `biomolecular-complementarity` study states).

---

## 4. Open risks / decisions for the plan

1. **Cahn-Hilliard scope (primary decision).** Recommend: **ship the cell-sorting core as the demonstrated claim; include a minimal separate CH process (verified, ~8 lines) as the "condensate" phase-separation analogue, honestly framed as an independent second demonstration, not coupled to the cells.** If keeping the increment tight, defer CH to a noted extension. Either way, do **not** couple φ to CPM (unverified, out of scope). CH is numerically stiff — pin `dt` small (`0.002` stable; `0.05` → NaN) and document the ∇⁴ stability limit.
2. **Metric needs a cohesion guard.** `hetero_frac` alone falsely reads 0.000 when the clump dissolves (T=400). Emit total cell-pixel count beside it; assert the clump stays cohesive over the run, and gate the "sorted" claim on both (fraction dropped **and** pixels retained). The behavior test should check `hetero_frac` t_end < ~0.2 **and** cell-pixels within ~10% of t0.
3. **Regime is tuned, not fitted.** The clean 1.000→0.12 sort depends on the J-triple (2/11/8) and T=10 staying in the narrow cohesive-and-mobile window; T and the medium-J are the fragile knobs (frozen below, dissolved above). Budget a short tuning pass if grid size / cell size / cell count change, and lock the reported regime in the composite params.

Lesser: sorting plateaus ~0.11 (residual two-domain boundary, not 0) — frame the claim as "heterotypic interface collapses by ~9×", not "goes to zero"; run length (~600 MCS) sets GIF cost; constant cell count means no growth-math zero-area guards are needed here.
