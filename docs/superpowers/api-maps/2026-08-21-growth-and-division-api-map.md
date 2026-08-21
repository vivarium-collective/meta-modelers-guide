# Code-verified API map — STUDY 8 `growth-and-division` (spatial)

**Date:** 2026-08-21
**Investigation:** `the-cellular-interface-multicellular`
**Analogue:** Fig 10a,b — a cell grows (volume target driven by metabolism) and **divides** at a threshold. Spatial analogue of the non-spatial `draft-to-living-cell` `growth-and-division` study (`workspace/studies/growth-and-division/study.yaml`, composites `fig10-1-*`), where an autocatalytic energy-coupled growth process drives a store across a threshold and fires a **place-graph rewrite** (1 cell node → 2 daughters, mass conserved) — "growth, not a timer, is what puts the cell at the division trigger."
**Verified against installed code:** `cpm` (`~/code/viva-cpm/cpm/`, Rust `cpm_core`; division source `~/code/viva-cpm/crates/cpm-core/src/mitosis.rs`, binding `crates/cpm-py/src/lib.rs:230`), the merged flagship `meta_modelers_guide/cpm/cell_field.py`, study-3 `colony_field.py`, and `cobra` textbook `e_coli_core`.
**Interpreter:** `~/code/meta-modelers-guide/.venv/bin/python`, `PYTHONPATH=<worktree>` (`~/code/meta-modelers-guide--cpm-multicellular`). Every snippet below was RUN; scratch scripts (`verify_div.py`, `verify_growth.py`, `verify_edge.py`) live in the session scratchpad.

---

## 1. Summary + recommended process shape + confirmed division mechanism

Study 8 is the spatial version of the non-spatial division study, but with a decisive win: **CPM division is a NATIVE, threshold-driven engine operation** — `world.divide_cells(threshold, reset_target)` — not a hand-rolled place-graph rewrite. It splits every non-medium cell whose lattice volume `>= threshold` by a plane perpendicular to the cell's longest bounding-box axis, **conserving mass** (pixels are re-owned, not duplicated), the parent keeping its id and a new id appearing for the other daughter. So the whole study is the flagship/colony growth loop **plus one extra call per tick**.

**Recommended process shape (one line):** ONE `CpmColonyField`-style world-owning process that each tick runs the flagship dFBA→biomass→`set_target_volume(cid, grow·biomass[cid])` growth body over every live cell id, `step()`s, then calls `world.divide_cells(vol_threshold, reset_target)` and folds the returned new ids into per-cell bookkeeping (`self.biomass[new_id] = biomass[parent]/2` or `= init`), re-deriving live ids from `np.unique(snapshot())` every tick.

**Confirmed division mechanism (crux resolved):**
- `divide_cells(threshold, reset_target)` divides **ALL** cells with `volume >= threshold` in one call (NOT a specified id, NOT "every cell"). To split *one* target cell, call it with a `threshold` only that cell has crossed — which is exactly what a growth-and-division loop does naturally: each cell divides on the tick its own growth carries it past `threshold`.
- **Daughter labeling:** the **parent keeps its id**; **one NEW id** is created (`add_cell`, same type/lambdas) for the other daughter. Not two new ids. Returns `Vec` of the new ids (creation order).
- **Geometry / mass:** split plane ⟂ the longest bbox axis through the bbox midpoint; pixels on the far side are re-owned to the new id → **mass conserved** (parent_vol + daughter_vol == pre-division vol). Both daughters' `target_volume` set to `reset_target` by the engine (no manual reset needed).
- **Trigger:** native threshold check inside `divide_cells` — the process does NOT need to poll `cell_volumes()[cid] >= t` itself; just call `divide_cells` each tick with the chosen threshold. Below-threshold cells are a clean no-op (empty return).

**Recommended growth mechanism: (a) reuse the flagship/colony dFBA shared-field path.** It makes "volume target driven by metabolism" literally true (matching the non-spatial study's honesty axis — growth is the mechanism that reaches the threshold, not a scripted ramp), and adds **no new dependency** (cobra is already the flagship's dep and the code is already written in `colony_field.py`). The only addition over `CpmColonyField` is the `divide_cells` call + daughter bookkeeping.

---

## 2. Verified API

### Q1 — `divide_cells`, the crux (RUN)

Source (`~/code/viva-cpm/crates/cpm-core/src/mitosis.rs:14-112`), quoted:

> Divide every non-medium cell whose volume >= threshold into two daughters, split by a plane perpendicular to the cell's longest bounding-box axis through the box midpoint. The original cell keeps its id (one daughter); a NEW cell (same type/lambdas) is the other. Both daughters' target_volume is set to `reset_target`. Returns the new daughter ids.

Binding: `crates/cpm-py/src/lib.rs:230` → `divide_cells(threshold, reset_target) -> Vec<u32>`. `help(world.divide_cells)` in Python confirms the two-arg signature.

RUN — seed one cell, grow it (`set_target_volume(1,150)` + `step`), then divide, then a second round (1→2→4):

```
before divide: n_cells= 1 ids= [0, 1] vols= [1452, 148]  coms=[medium, (19.7,19.9)]
divide_cells(80.0, 40.0) returned new_ids= [2]
after divide:  n_cells= 2 ids= [0, 1, 2] vols= [1452, 71, 77]   # 71+77 == 148 (mass conserved)
  coms= [medium, (16.6,20.2), (22.5,19.6)]                       # daughters flank the split plane

# second round: grow ids 1 AND 2 back to 150, divide again
grown: n_cells= 2 vols= [1300, 150, 150]
divide_cells(80.0,40.0) returned= [3, 4]                          # TWO new ids (one per parent)
after 2nd divide: n_cells= 4 ids= [0,1,2,3,4] vols= [1300, 89, 71, 61, 79]
ids after 20 further steps: [0,1,2,3,4] n_cells= 4               # ids stable across steps
```

**Confirmed:** parent id 1 persists; a single new id (2) appears; volume splits ~in half with mass conserved; it compounds (1→2→4, new ids 3 & 4 from parents 1 & 2). Ids are stable across subsequent `step()`s. `n_cells()` = `cells.len() - 1` and **does increment** on division (unlike the `remove_cells` quirk) because `divide_cells` calls `add_cell`.

**How a process splits one cell at a threshold:** call `world.divide_cells(vol_threshold, reset_target)` once per tick after `step()`. Any cell whose grown volume reached `vol_threshold` splits; the rest no-op. There is no per-id division call — targeting is done through the threshold + the cell's own growth.

### Q2 — Growth mechanism → recommend (a) (RUN)

The flagship's cobra path drives volume up cleanly. RUN dFBA growth curve (`e_coli_core`, `EX_o2_e=-15`, abundant glucose, `target_vol = 300·biomass`):

```
tick biomass  target_vol
  0   0.170      50.9
  1   0.240      72.0
  2   0.340     101.9  <-- crosses division threshold 90
  ...
 13  15.403    4621.0   (mu=0.6908 at abundant glucose -> exponential biomass rise)
```

Metabolism drives target volume monotonically up and across a threshold (option **a**). Option **(c)** scripted ramp also works and gives the cleanest textbook sawtooth (Q5 run), but it is **not** metabolism-driven and would break the non-spatial study's honesty framing ("growth, not a timer"). Option **(b)** nutrient-field-proportional (no cobra) is a lighter honest middle ground but still needs a field and is less faithful to "driven by metabolism."

**Recommendation: (a).** It reuses `colony_field.py` verbatim (no new dep — cobra already required), and its nutrient-limited clamp keeps growth bounded and plateauing as the shared field depletes (the flagship's mass-balance, `cell_field.py:156-176`) — which is realistic but means **the field must be replenished or large enough** for cells to keep re-crossing the threshold across generations (see Risks). A pure unlimited-glucose curve grows *exponentially* (4621 by tick 13 above), which drives repeated division but must be reined in by the field coupling.

### Q3 — Division trigger: NATIVE, no manual poll (RUN)

Unlike the disintegration study (which had to poll a footprint mean and latch), division needs **no manual `cell_volumes()[cid] >= t` check**: the threshold test lives inside `divide_cells`. Below-threshold is a verified clean no-op (Rust test `below_threshold_does_not_divide`, and the Q5 run where a cell at vol 87 < 90 simply did not divide that round while its siblings did). **Recommended trigger design:** call `divide_cells(vol_threshold, reset_target)` every tick after `step()`; pick `vol_threshold` ≈ 2× the settled `reset_target` so a daughter must roughly double before re-dividing.

### Q4 — Multi-generation bookkeeping (RUN)

Daughters get sensible targets **automatically** — the engine sets both daughters' `target_volume = reset_target`, so **no manual `set_target_volume` reset is required** to prevent immediate re-division or collapse:

```
# post-divide, targets NOT touched by the process, just stepped:
after divide:              vols= [1452, 71, 77]
after 30 steps post-divide vols= [1523, 38, 39]   # both relaxed toward reset_target 40, stable
```

Ids are stable across steps (Q1). A second and third round compound correctly (Q1: 1→2→4; Q5: 1→2→4→7). **The one bookkeeping duty on the process:** when `divide_cells` returns new ids, seed their per-cell state (`self.biomass[new_id]`) — split the parent's biomass in half (mass-honest) or set to an init value — and add them to the per-cell loop. Re-derive live ids from `np.unique(snapshot())` each tick (as `colony_field.py:242` already does), because `n_cells()` can over-count phantom zero-volume daughters (Q6).

### Q5 — Observables + the demonstrating metric (RUN)

End-to-end sawtooth/staircase, RUN with a scripted ramp standing in for the metabolism driver (to isolate the growth+divide loop; the metabolism driver is Q2):

```
t= 1 n_cells=1 total_area= 45  per_cell=[45]
t= 7 n_cells=1 total_area= 84  per_cell=[84]
t= 8 n_cells=2 total_area= 93  per_cell=[40, 53]   <-- DIVISION new=[2]   (per-cell vol drops ~half)
t=15 n_cells=2 total_area=167  per_cell=[84, 83]
t=16 n_cells=4 total_area=183  per_cell=[55,46,37,45] <-- DIVISION new=[3,4]
t=23 n_cells=4 total_area=336  per_cell=[82,84,85,85]
t=24 n_cells=7 total_area=366  per_cell=[51,87,43,41,42,49,53] <-- DIVISION new=[5,6,7]  (only 3 of 4 crossed)
final ids: [1,2,3,4,5,6,7]  n_cells: 7
```

Emit per tick: `n_cells` (staircase 1→2→4→…), **per-cell volume** (`cell_volumes()[cid]`, sawtooth: ramp → halve on division), `total_area`/total biomass (net-rising staircase), `position` (`cell_coms()[cid][:2]`), per-cell `biomass`/`local_nutrient` (from the dFBA path), and **division-event ticks** + the new ids returned by `divide_cells` (for lineage: `parent_of[new_id]` = the id it was created alongside). Generation is derivable by tracking a `gen[cid]` incremented for both daughters at each split.

**Demonstrating signal:** per-cell volume sawtooth (grows to `~threshold`, halves at each division) against the `n_cells` staircase — exactly Fig 10a,b. Note the `4→7` step: division fires per-cell independently, so a cell that hasn't *quite* reached threshold sits out that round — a faithful, not a bug, consequence of "divides all cells ≥ threshold."

### Q6 — Gotchas specific to this study (RUN)

- **Dividing a too-small cell makes a 0-volume phantom daughter (does NOT crash).** RUN:
  ```
  tiny 4px  -> divide(4,2): new=[2] vols=[.,2,2]           # fine, both real
  thin 1x8  -> divide(6,4): new=[2] vols=[.,4,4]           # fine, splits along long axis
  single 1px-> divide(1,1): new=[2] vols=[.,1,0] ids=[1]   # daughter got 0 px: PHANTOM
     after 5 steps: vols=[.,0,0] ids=[] n_cells=2          # n_cells over-counts; no live footprint
  ```
  So `divide_cells` never crashes on a tiny cell, but if the split plane leaves one side empty it creates a **zero-volume phantom** that inflates `n_cells()` without a snapshot footprint. **Keep `vol_threshold` comfortably above ~8 px** (both daughters need real area) and **always re-derive live ids from `np.unique(snapshot())`** rather than trusting `n_cells()`.
- **No manual daughter target reset needed** (Q4) — the engine sets both to `reset_target`; do NOT double-reset to something that triggers immediate re-division (keep `reset_target` well below `vol_threshold`).
- **Grid must be big enough for the final generation.** 4+ cells each settling near `reset_target` need lattice room; the flagship's 40×40 held 7 cells at area ~48 each (Q5 used 50×50). Size `dims` for `2^gens · reset_target` pixels plus medium, or growth stalls from crowding / domination.
- **`seed_block` half-open, `z0,z1 = 0,1` for 2D** (carried constraint). Single initial cell → no seed-overlap concern.
- **Connectivity (E1) is a no-op in this build** (disintegration Q1) — do NOT expect it to keep daughters coherent; the volume constraint (`lambda_volume`) + positive contact J + moderate temperature (10–12) supply coherence. Set `{a:1,b:1,j:…}` cell↔cell contact so daughters don't over-fuse or over-repel (study-3 Q8).
- **`cell_volumes()`/`cell_coms()`/`cell_lengths()` are LISTS indexed by id, element [0] = medium** (study-3 Q1); use `[cid]`, never `.get()`.
- A **length-based** trigger is also available if desired: `cell_lengths()` returns per-id major-axis length (RUN: a 1×8 strip read length 7.94), and `divide_cells` is volume-thresholded only — there is no native length-threshold divide, so length would have to be polled manually. Volume threshold (native) is simpler; recommend it.

---

## 3. Carried-over constraints (still binding)

- **Worktree discipline:** all work in `<worktree>` (`~/code/meta-modelers-guide--cpm-multicellular`); `PYTHONPATH` prepended; venv interpreter above. Read-only except this one file.
- **Full import-path process addresses:** `local:!spatio_flux.processes.diffusion_advection.DiffusionAdvection` (bare `local:DiffusionAdvection` collides with `viva_munk`); in-repo processes register via `build_core()`.
- **Shared-grid contract:** all arrays `(ny,nx)` = (rows, cols); x=cols, y=rows; CPM dims == spatio-flux `n_bins`; `snapshot()`/`field_conc()` are flat `x + y·nx` → reshape `(ny,nx)`; spatio-flux needs square cells.
- **dFBA path unchanged from flagship/colony:** `load_model("textbook")`, set `EX_glc__D_e.lower_bound` (MM-limited each tick), `EX_o2_e.lower_bound = -oxygen_vmax` (default 15) to force acetate overflow, read `sol.fluxes` **only when `sol.status == "optimal"`** (stale primal on infeasible re-solve). One cobra model **per cell** (colony_field pattern) to avoid bound leakage between daughters.
- **Mass-balance growth clamp** (`cell_field.py:156-176`): scale biomass by however much substrate removal was clamped — growth plateaus as the field depletes (relevant here, see Risk 1).
- **`overwrite[...]` on absolute observables:** per-cell `volume`, `position`, `local_nutrient`, `biomass`, `n_cells` are per-tick absolute readings → declare `overwrite[...]` (plain `float`/`list` apply is additive/concatenating). Division-event counters that are genuine per-tick deltas stay plain additive.
- **Runtime mutation surface** (disintegration Q3): only `set_target_volume`, `set_contact`, `set_cell_type`, `set_length_constraint`, `set_external_potential`, `remove_cells`, `divide_cells`. `lambda_volume`/`lambda_surface`/`temperature` are **init-only**.
- **Toy-real:** plausible constants, not a fitted organism; honest framing (mirror the non-spatial study's "growth is the mechanism that reaches the threshold, not a scripted ramp").

---

## 4. Open risks / decisions for the plan

1. **Sustaining division across generations under nutrient limitation.** The honest dFBA path (option a) plateaus as the shared glucose field depletes (mass-balance clamp), so without replenishment a cell may grow, divide once or twice, then stall below threshold — a *thinner* staircase than Fig 10b. **Decide:** either (i) replenish glucose (a `DiffusionAdvection` source term / periodic top-up) so daughters keep re-crossing the threshold, or (ii) tune a large initial reservoir + few generations (1→2→4 is enough to demonstrate the mechanism), or (iii) accept a scripted/nutrient-proportional growth (b/c) if a clean multi-round sawtooth matters more than metabolic fidelity. Recommend (i)+(ii): abundant/replenished field, target ~2–3 division rounds.
2. **Phantom zero-volume daughters + `n_cells()` over-count.** Dividing a cell too small to split cleanly creates a 0-volume daughter that inflates `n_cells()` with no footprint (Q6). **The plan must:** floor `vol_threshold` well above ~8 px, keep `reset_target` low enough that a daughter has room to grow but high enough to be splittable, and re-derive live ids from `np.unique(snapshot())` every tick (never trust `n_cells()` for the per-cell loop).
3. **Threshold/reset/grid co-tuning for a legible sawtooth.** The demonstrating signal needs `vol_threshold ≈ 2·reset_target`, a `grow_per_biomass`/ramp slow enough to see the ramp (not jump the threshold in one tick), and a grid sized for the final generation without crowding-induced domination (Q6). Budget a short tuning pass; Q5's 50×50, threshold 90, reset 45, ~+6/tick ramp gave a clean 1→2→4→7 staircase as a starting point.

Lesser: set `{a:1,b:1,j:…}` cell↔cell contact so daughters neither fuse nor scatter (study-3 Q8); moderate init temperature 10–12 for coherent daughters (connectivity E1 is a no-op — disintegration Q2); lineage/generation tracking is derivable from `divide_cells` return values but is bookkeeping the process must add itself (no native lineage).
