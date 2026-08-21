# Code-verified API map — STUDY 3 `cell-cell-coupling` (spatial)

**Date:** 2026-08-21
**Investigation:** `the-cellular-interface-multicellular`
**Analogue:** the paper's §Cell–cell coupling viability negotiation (no dedicated figure) → spatial competitive exclusion + cross-feeding
**Verified against installed code:** `cpm` (`~/code/viva-cpm/cpm/`, Rust `cpm_core`), `cobra` textbook `e_coli_core`, and the merged flagship `meta_modelers_guide/cpm/cell_field.py`.
**Interpreter:** `~/code/meta-modelers-guide/.venv/bin/python`, `PYTHONPATH=<worktree>`.

---

## 1. Summary + recommended process shape

The flagship's single-cell design generalizes to N cells **without a new abstraction**: one CPM `World` already hosts N distinct cells on the same shared lattice, they compete for space automatically, and every per-cell control the flagship uses (`snapshot()` footprint mask, `cell_coms()`, `cell_volumes()`, `set_target_volume(cid, …)`) is already **indexed by cell id**. cobra `e_coli_core` supplies both regimes off the flagship's existing dFBA path: two glucose competitors are just two glucose bounds; cross-feeding is a glucose→acetate secretor (O2-capped, as the flagship already does) plus a consumer with glucose off and `EX_ac_e` lower bound flipped negative to take acetate up.

**Recommended process shape (one line):** ONE `CpmCellField`-style process that owns ONE CPM world holding N cells, looping the flagship's read-field → dFBA → writeback → set-target-volume body over each cell id (option (a)); N separate world-owning processes is wrong because CPM cells must share a single lattice to interact.

Everything below is backed by a snippet that was actually run; scratch scripts live in the session scratchpad (`verify.py`, `verify_fba.py`).

---

## 2. Verified API

### Q1 — Multiple cells in one CPM world

`cpm.schema.load_world` (read: `cpm/schema.py:29-60`) iterates `spec["cells"]`, calling `world.add_cell(...)` per entry (returns a fresh integer id) then `world.seed_block(cid, x0,y0,z0, x1,y1,z1)` for each. So **N cells = N entries under `cells`, each with its own half-open `seed_block`.** The `cells` and `seed_labels` paths are mutually exclusive.

Verified spec that seeds 2 non-overlapping cells on a 60×60 lattice, then stepped:

```python
NX = NY = 60
spec = {
  "potts": {"dims": [NX, NY, 1], "boundary": "noflux", "neighbor_order": 2,
            "temperature": 10.0, "seed": 1},
  "cells": [
    {"type": 1, "target_volume": 60.0, "lambda_volume": 2.0,
     "target_surface": 0.0, "lambda_surface": 0.0, "seed_block": [12, 26, 0, 20, 34, 1]},
    {"type": 1, "target_volume": 60.0, "lambda_volume": 2.0,
     "target_surface": 0.0, "lambda_surface": 0.0, "seed_block": [40, 26, 0, 48, 34, 1]},
  ],
  "contact": [{"a": 0, "b": 1, "j": 14.0}, {"a": 1, "b": 1, "j": 14.0}],
}
w = load_world(spec); w.step(10)
```

Real output:
```
n_cells: 2
cell_types: [0, 1, 1]                      # list indexed by id; index 0 = medium (type 0)
unique ids in snapshot BEFORE step: [0 1 2]
unique ids in snapshot AFTER step 10: [0 1 2]
cell_coms(): [(29.50, 29.49, 0.0), (15.16, 29.63, 0.0), (43.79, 29.77, 0.0)]
cell_volumes(): [3488, 56, 56]
```

**The two cells are labeled by distinct integer ids `1` and `2` in `snapshot()`** (id `0` = medium). Ids are assigned sequentially in `cells`-list order (first entry → id 1).

**IMPORTANT correction to the task's premise:** `cell_coms()` / `cell_volumes()` / `cell_types()` return a **Python `list` indexed by cell id, NOT a dict** — and **element `[0]` is the MEDIUM** (its COM is the whole-lattice centroid ~ (29.5, 29.5); its "volume" 3488 is the medium pixel count). So per-cell values are `cell_coms()[1]`, `cell_coms()[2]`, … exactly as the flagship's `world.cell_coms()[1]` already does. Do NOT call `.keys()` / `.get()` on these — that raises `AttributeError`.

### Q2 — Per-cell footprint

Reshape the flat snapshot to `(ny, nx)` (shared-grid contract) and mask by id — same as the flagship's `_footprint()` but per id:

```python
lat = np.array(w.snapshot()).reshape(NY, NX)
fp1, fp2 = (lat == 1), (lat == 2)
```

Real output (after Q1's `step(10)`):
```
cell 1: area=56, bbox x[11-19] y[25-33]
cell 2: area=56, bbox x[40-47] y[26-34]
ids from snapshot: [1, 2]
com[1]= (15.16, 29.63, 0.0)   com[2]= (43.79, 29.77, 0.0)
```

Footprint bbox matches each cell's `seed_block` x-range and its `cell_coms()[cid]` — **snapshot ids, `cell_coms()` ids, and `set_target_volume(cid,…)` ids are the same id space.** `fp.sum()` equals `cell_volumes()[cid]` (56).

### Q3 — Per-cell growth (independent targets)

`world.set_target_volume(cid, value)` is per-id; the flagship calls it for id 1. Setting divergent targets for ids 1 and 2 then stepping:

```python
w.set_target_volume(1, 120.0); w.set_target_volume(2, 30.0); w.step(30)
```
Real output:
```
after divergent targets (cell1=120, cell2=30) volumes: [3456, 118, 26]
areas from snapshot: cell1= 118  cell2= 26
```

Cell 1 grew toward 120, cell 2 shrank toward 30 — **independent per-cell target volumes confirmed.** This is the exact lever for the competition regime (drive each cell's target from its own dFBA biomass).

### Q4 — Process shape decision → single world-owning process (option a)

The Q1/Q3 output *is* the evidence: **a single `World` naturally hosts N interacting cells that share one lattice and compete for space** (with divergent targets one cell claimed pixels while the other gave them up; total lattice is conserved). The lattice and growth are not process-bigraph stores (flagship module docstring, `cell_field.py:1-9`), so they can only be driven from inside the process that owns the world. N separate world-owning processes would each hold a *disjoint* lattice — the cells could never touch, compete for space, or share footprint-local field pixels through the CPM geometry. **Recommendation: generalize `CpmCellField` to own one world with N cells and loop the flagship's `update()` body over `for cid in cell_ids:`** (read field at `lat==cid`, dFBA with that cell's bounds, write that cell's delta, `set_target_volume(cid, grow*biomass[cid])`), tracking a per-cell `self.biomass[cid]`. One `world.step(mcs)` per tick after all cells' targets are set.

### Q5 — Per-cell dFBA config for the two regimes

Reuses the flagship's cobra path verbatim (`cell_field.py:_fba`, `load_model("textbook")`, set `EX_glc__D_e.lower_bound`, read `sol.fluxes["EX_glc__D_e"|"EX_ac_e"]`). The distinguishing knobs are exchange lower bounds. Default bounds (verified): `EX_glc__D_e` `[-10, 1000]`, `EX_ac_e` `[0, 1000]` (**acetate secrete-only by default**), `EX_o2_e` `[-1000, 1000]`.

**(a) Two glucose competitors** — same model, different glucose vmax (and/or different lattice position on the gradient), flagship's `EX_o2_e = -15` microaerobic cap kept:
```
competitor A (glc vmax 10): status=optimal mu=0.7178 EX_glc=-10.000 EX_ac=6.811 EX_o2=-15.000
competitor B (glc vmax 4):  status=optimal mu=0.3239 EX_glc=-4.000  EX_ac=0.000  EX_o2=-9.840
```
The higher-uptake cell grows ~2.2× faster — its target volume outruns the other's → competitive exclusion for both shared glucose and lattice space.

**(b) Cross-feeding — secretor + consumer:**
```
SECRETOR (glc=10, o2cap=15): status=optimal mu=0.7178 EX_glc=-10.000 EX_ac=+6.811  EX_o2=-15.000
   -> EX_ac_e > 0 means it secretes acetate: True
CONSUMER (glc=0, ac uptake<=10, o2=20): status=optimal mu=0.1733 EX_glc=0.000 EX_ac=-10.000 EX_o2=-12.423
   -> EX_ac_e < 0 means it consumes acetate: True
   -> consumer still grows on acetate alone: True
```
Minimal consumer parameterization: `EX_glc__D_e.lower_bound = 0.0` (glucose off), `EX_ac_e.lower_bound = -v_ac` (**flip the default 0 negative → acetate UPTAKE**), `EX_o2_e.lower_bound = -20` (acetate must be respired, so the consumer needs O2 *uncapped*, unlike the secretor). **Confirmed: the acetate exchange id is `EX_ac_e`, and reversing its lower bound to a negative value lets a cell consume acetate and grow on it alone (μ=0.17).** The consumer reads acetate at its footprint from the shared `fields["acetate"]` array (which `DiffusionAdvection` has spread from the secretor's plume) and MM-limits its acetate vmax on that local concentration, mirroring the flagship's glucose MM logic.

### Q6 — Shared field routing (N cells → one `fields` store)

The flagship returns `{"fields": {"glucose": dglc, "acetate": dace}}` where each is a full `(ny,nx)` array nonzero only on the footprint; `fields` is declared `map[array]` and process-bigraph **sums** these into the shared grid (flagship `outputs()` docstring, `cell_field.py:54-68`: "`fields` is a real spatial delta the engine sums into the shared grid"). For N cells in ONE process, the process returns a **single combined delta array** = sum of per-cell contributions (each cell writes only its own footprint pixels).

**Mass-conservation is safe for disjoint footprints, which CPM guarantees:** every lattice pixel belongs to exactly one cell id (or medium), so no two cells' footprints overlap and no glucose pixel is claimed twice in a tick. Each cell must still clamp its own removal against `glucose[fp_cid].sum()` (its own pixels) exactly as the flagship does (`cell_field.py:156-176`, per-pixel proportional writeback). **Concern to flag for the plan:** when two footprints are *adjacent* (touching but not overlapping) they remain disjoint so summation is still correct; the only real risk is if the implementation ever reads the field once but writes cell-by-cell against a *stale* per-cell sum — read the field snapshot once at tick start and clamp each cell against its own disjoint pixel set (no interaction), which is automatically true within a single `update()`.

*Not runtime-verified end-to-end:* I did not build a 2-cell Composite and step it through process-bigraph (that is implementation, not yet written). The additive-`map[array]` behavior is verified only via the flagship's existing single-cell semantics + its authored docstring, not via a two-writer run. **Flag: the plan's first task should assert two disjoint deltas sum correctly in a real Composite.**

### Q7 — Observables and the demonstrating metric

Emit, **per cell id**, the flagship's five scalars: `volume` (`cell_volumes()[cid]`), `position`/COM (`cell_coms()[cid]`), `local_nutrient` (mean glucose over `lat==cid`), `biomass` (`self.biomass[cid]`), and acetate uptake/secretion (`EX_ac_e` flux sign, or the per-cell `dace.sum()`). For the consumer also emit local acetate. Structure as `obs[cid][...]` or parallel arrays.

- **Competitive exclusion metric:** *divergent biomass/volume trajectories* — the winner's biomass & volume rise while the loser's plateau or shrink (Q3 already shows volumes 118 vs 26 diverging), with total shared glucose monotonically depleting.
- **Cross-feeding metric:** *both cells stay viable via an acetate handoff* — secretor `EX_ac_e > 0` and its acetate plume rising; consumer `EX_ac_e < 0`, its local acetate rising then being drawn down, and its biomass staying positive even though its local glucose is ~0. The demonstrating signal is the anticorrelation: consumer biomass tracks the arriving acetate, not glucose.

### Q8 — Multi-cell gotchas (not hit by the flagship)

- **`cell_coms()`/`cell_volumes()` are lists, index 0 = medium** (Q1). Any per-cell loop must iterate ids `1..n_cells`, skipping 0, and must not treat these as dicts.
- **Id stability across steps:** ids `1,2` persisted across all steps in every run — CPM tracks cell *identity*, not just type; two `type: 1` cells keep distinct ids. Safe to key per-cell biomass by id for the whole run (barring division/removal).
- **A cell shrinking to zero:** `set_target_volume(cid, 0.0)` is accepted and drives the cell's volume/area to **0** cleanly (verified: `volumes [3542, 58, 0]`, cell-2 snapshot area 0) — the id *slot persists* (still indexed, volume 0). This is the recommended "stall/death" mechanism for the losing competitor: floor the target at 0 (or a small value), do NOT remove. Growth math must guard against divide-by-area-0 (flagship already does `area = max(fp.sum(), 1)`).
- **`remove_cells([cid])` is quirky:** it removes the pixels (snapshot ids drop to `[0,1]`, `cell_coms()[2]` → `(0,0,0)`) but `n_cells()` did **not** decrement (stayed 2) and the id slot lingers as a zeroed entry. Prefer target_volume→0 over `remove_cells` for a cell "dying"; if removal is truly needed, re-derive live ids from `np.unique(snapshot)` rather than trusting `n_cells()`.
- **Contact energies between two type-1 cells:** the flagship only set `contact [{a:0,b:1,j:14}]` (medium↔cell). With two same-type cells you should also set the **`{a:1,b:1,j:…}`** (cell↔cell) adhesion — verified `set_contact` accepts `a==b`. Omitting it leaves the type1↔type1 J at the engine default; tune it to control whether the two cells stick, stay apart, or sort. Lower J = stronger adhesion (cells hug); higher J = they avoid contact.
- **Non-overlapping seeding:** `seed_block`s must not overlap (half-open ranges, `z1=1` for 2D per the flagship constraint). Overlapping blocks would let one cell's seed overwrite another; keep a gap so diffusion (not seed collision) mediates early interaction.

---

## 3. Carried-over constraints (flagship Global Constraints that still apply)

From `docs/superpowers/plans/2026-08-21-flagship-single-cell-in-a-field.md` §Global Constraints — all still binding:

- **Worktree discipline:** all work in `~/code/meta-modelers-guide--cpm-multicellular`; `PYTHONPATH` prepended; venv interpreter as above.
- **Full import-path process addresses:** `local:!cpm.processes.cpm_process.CPMProcess`, `local:!spatio_flux.processes.diffusion_advection.DiffusionAdvection`, `local:!spatio_flux.processes.dfba.SpatialDFBA`/`.DynamicFBA`. Bare `local:DiffusionAdvection` resolves to the wrong package (`viva_munk` collision); bare `local:CPMProcess` does not resolve. In-repo processes (the generalized `CpmCellField`) register via `build_core()`.
- **Shared-grid contract:** all arrays `(ny, nx)` = (rows, cols); x=cols, y=rows; CPM dims == spatio-flux `n_bins`; `snapshot()`/`field_conc()` are flat `x + y*nx` → reshape `(ny, nx)`; spatio-flux needs square cells (`bounds == n_bins`).
- **`seed_block` half-open, `z0,z1 = 0,1` for 2D** (`z1=0` → empty world); `[x0,y0,z0, x1,y1,z1]`, `x1=x0+width`.
- **`DiffusionAdvection`/`DynamicFBA` `update()` return DELTAS** the engine applies to the store; likewise `CpmCellField`'s `fields` output is a summed spatial delta.
- **The Rust CPM internal field is write-protected** — the metabolized nutrient lives in the writable spatio-flux `fields` store, not the CPM field. CPM-native chemotaxis (Rust) stays out of scope.
- **`overwrite[...]` on absolute observables:** `volume`, `position`, `local_nutrient`, `biomass` are per-tick absolute readings and MUST be declared `overwrite[...]` (plain `float`/`list` apply is additive/concatenating). Per-cell observables inherit this — with N cells emit them as `overwrite` per cell. `acetate_secreted` stays plain additive `float` (genuine per-tick delta).
- **O2 cap forces overflow:** `EX_o2_e.lower_bound = -oxygen_vmax` (default 15) is what makes any secretor emit acetate; unbounded O2 → pure respiration → `EX_ac_e = 0` (flagship module docstring, re-verified in Q5).
- **Trust `sol.fluxes` only when `sol.status == "optimal"`** — an infeasible re-solve returns stale primal values (flagship `_fba`, `cell_field.py:117-128`). Carry the same guard per cell.
- **Toy-real:** plausible constants, not a fitted organism; keep the honest-framing conventions.

---

## 4. Open risks / decisions for the plan

1. **Additive two-writer field delta is not yet runtime-verified** (Q6). The additive `map[array]` sum is only inferred from the flagship's single-writer semantics + docstring. **First plan task must build a real 2-cell Composite and assert that two disjoint footprint deltas sum into `fields` correctly and conserve mass** before trusting the competition/cross-feeding numbers.
2. **Per-cell dFBA model instances vs one shared model with reset bounds.** The flagship holds one `self._model`. With N cells having *different* bounds (esp. cross-feeding: secretor O2-capped/glucose-on, consumer O2-open/glucose-off/acetate-on), reusing one model object means re-setting all relevant bounds every cell every tick, and any missed bound leaks between cells. **Decide: one cobra model per cell (N `load_model` copies, cleaner, more memory) vs one model with a full per-cell bound-reset block (leaner, error-prone).** Given only 2–4 cells, per-cell model copies are the safer default.
3. **Regime tuning / competitive-exclusion legibility.** Whether exclusion is *visible* over a ~20-tick run depends on gradient shape, seed positions, `grow_per_biomass`, and the uptake asymmetry (Q5 shows μ 0.72 vs 0.32 — a real but not dramatic gap). Cross-feeding also needs the consumer's acetate to actually diffuse to it before it starves (diffusion coeff vs inter-cell distance). **Plan must budget a tuning pass; may need position advantage + uptake advantage stacked for a clean exclusion GIF, and a secretor→consumer spacing where the acetate plume reaches the consumer's footprint.**

Lesser risks: `remove_cells` id-slot quirk (Q8 — prefer target→0); type1↔type1 contact J is an unset default that must be chosen (Q8); guarding growth math against zero-area cells (Q8).
