# Code-verified API map — STUDY 9 `development-and-evolution` (spatial)

**Date:** 2026-08-22
**Investigation:** `the-cellular-interface-multicellular`
**Analogue:** Fig 10c–f — **development** (individual cellular interfaces become embedded in a *collective* interface defined by shared state — a depleted core vs a fed rim, physiological heterogeneity; stewart2008/flemming2016) and **evolution** (heritable variation under selection shifts a population trait). Spatial analogue of the non-spatial `draft-to-living-cell/development-and-evolution` study, whose own verdict was explicit that its selection was "a single ODE with fixed viability/fitness constants" and its "new port" a config ramp — *pattern, not phenomenon*. Study 9 is the capstone: pin a concrete, runnable, HONEST realization of BOTH halves on the real dividing colony.
**Base extended:** `meta_modelers_guide/cpm/growth_division.py` (`CpmGrowthDivision`, study 8) — a colony growing by per-cell dFBA on a shared glucose field, dividing via native `world.divide_cells`, with per-cell `biomass` + `generation`/`lineage` bookkeeping. Study 8 already **partitions biomass** on division (proportional to post-split volume) and **records a real genealogy** via the mitosis.rs creation-order pairing (`zip(dividing, new_ids)`), verified in `docs/superpowers/api-maps/2026-08-21-growth-and-division-api-map.md`. Study 9 adds ONE thing: a **heritable per-cell trait** carried through that same pairing.
**Verified against installed code:** `cpm` (viva-cpm, native `divide_cells` + `mitosis.rs`), `cobra` (`e_coli_core` dFBA), `spatio_flux` (`DiffusionAdvection` field). Interpreter `<repo>/.venv/bin/python`, `PYTHONPATH=<worktree>` (`~/code/meta-modelers-guide--cpm-multicellular`). Every number below was RUN. Scratch scripts (`dev_hetero.py`, `cpm_evo.py` = a `CpmEvolution(CpmGrowthDivision)` prototype, `run_evo.py`, `dbg_pair.py`) live in the session scratchpad — **not committed**; the prototype is the reference for the plan's process, not a merged artifact.

---

## 1. Summary + recommended process shape + confirmed contrasts

Study 9 needs no new mechanism and no new dependency: it is `CpmGrowthDivision` **plus a per-cell heritable scalar**. Both halves fall out of the shared-field coupling that study 8 already runs — development is that coupling *measured radially*, evolution is that coupling *selecting on an inherited trait*.

**Recommended process shape (one line):** ONE `CpmEvolution(CpmGrowthDivision)` world-owning process that reuses study 8's dFBA-growth + native `divide_cells` loop unchanged, ADDS a per-cell heritable `self.vmax[cid]` (used as that cell's glucose-uptake `vmax` in its own dFBA solve), mutates it on division inside the existing creation-order `zip(dividing, new_ids)` pairing (`daughter_vmax = parent_vmax + N(0,σ)`, deterministic RNG seeded from config; parent keeps its trait), and emits a **radial core-vs-rim heterogeneity** metric (development) plus **population mean/variance of the trait** (evolution).

**Confirmed contrasts (both RUN, numbers in §2):**

- **DEVELOPMENT — heterogeneity EMERGES from the shared field (not imposed).** On the *existing* study-8 colony (base composite, `glucose_vmax` 1.5, 60×60), binning live cells by distance from the colony centroid (median split into core/rim) and comparing each group's mean `local_glucose`: the rim/core glucose ratio grows **1.003 → 1.096** and the rim−core difference **+0.036 → +0.97** as the colony develops from 2 → 17 cells (tick 9 → 36). Early colony ≈ uniform; late colony has a measurably depleted core and a fed rim. No structure is imposed — it is the same shared-field mass-balance that produced study 8's division desync, now read as a spatial gradient.
- **EVOLUTION — mean trait shifts UP under selection, NOT in the controls (multi-seed).** Founder `vmax` 1.5, Gaussian mutation σ=0.3 on division, 45-tick run, seeds 1–5:
  - **Selection ON:** population mean `vmax` shifts **UP in 4/5 seeds** (Δ range **[−0.116, +0.700]**, mean **+0.221**); variance builds 0.10–0.52; higher-uptake populations also reach more cells (24–70).
  - **Control, no mutation:** mean stays **exactly 1.500** (Δ=0.000, var=0.000) in **0/5** seeds — no raw material, no shift.
  - **Control, no selection (trait made fitness-neutral):** mean drifts *undirected*, **2/5** up, mean **−0.039** — mutation without selection gives no directional shift.

The honest multi-seed signal is exactly the convention's shape: *"shifts up in ≥4/5 seeds under selection, 0/5 in the no-mutation control, undirected (2/5) in the no-selection control."*

---

## 2. Verified API (the 7 questions)

### Q1 — Development heterogeneity, MEASURED (RUN)

No new code needed — the metric runs on the committed base composite. Bin live cells by Euclidean distance of `obs.position` from the colony centroid, median-split into core (≤ median) and rim (> median), compare mean `obs.local_glucose`:

```
tick n_cells  g_core   g_rim    rim-core  rim/core
   9     2   11.3676  11.4037   +0.0360   1.003     <- early: ~uniform
  18     4   10.9801  11.0229   +0.0428   1.004
  24     7   10.7158  10.9381   +0.2223   1.021
  27     8   10.5406  10.9762   +0.4355   1.041
  33    14   10.1184  11.0297   +0.9113   1.090
  36    17   10.1584  11.1312   +0.9728   1.096     <- late: core depleted, rim fed
```

The core−rim gap grows **~27×** (0.036 → 0.97) as the colony develops — physiological heterogeneity **emerging** from shared-field competition, the "collective interface" of Fig 10c–d and the growth-and-division study's own next-step ("a center-vs-edge growth-rate readout … rather than inferring it from staircase desync alone"). **Honest caveat:** at `glucose_vmax` 1.5 the *absolute* depletion is weak (rim/core only ≈1.10 at the end — the same ~3% field-wide dip study 8 flagged), so the gradient is real and monotone but shallow; a leaner field or higher `vmax` sharpens it at the cost of faster crowding (Risk 3). Per-cell growth/biomass rate vs radius is an equivalent readout on the same `position`+`biomass` observables.

### Q2 — Heritable trait + inheritance-on-division, the evolution crux (RUN)

Prototype `CpmEvolution(CpmGrowthDivision)` adds `self.vmax: dict[int,float]` (founder seeded at `trait_init`), overrides `_fba` to use `self.vmax[cid]` as the MM uptake `vmax`, and — in study 8's existing `zip(dividing, new_ids)` loop — sets `self.vmax[daughter] = clip(self.vmax[parent] + rng.normal(0,σ))` while the parent keeps its trait. Selection is emergent: higher `vmax` → more glucose → faster biomass → crosses `vol_threshold` sooner → divides more → that trait proliferates.

Mean-trait trajectory, 45 ticks, founder 1.5, σ=0.3, seeds 1–5 (config echo confirmed the effective config each arm):

```
SELECTION (selection ON, mutation ON)
 seed 1: n->50 gen6  mean 1.500->1.687 (+0.187) var0.115
 seed 2: n->42 gen6  mean 1.500->1.719 (+0.219) var0.161
 seed 3: n->70 gen6  mean 1.500->2.200 (+0.700) var0.515
 seed 4: n->37 gen5  mean 1.500->1.617 (+0.117) var0.175
 seed 5: n->24 gen4  mean 1.500->1.384 (-0.116) var0.101
 -> UP in 4/5; delta range [-0.116,+0.700], mean +0.221

CONTROL no-mutation (mutation_off=True)
 all 5 seeds: mean 1.500->1.500 (+0.000) var0.000   -> UP in 0/5

CONTROL no-selection (trait fitness-neutral; mutation still ON)
 seed1 +0.112 / seed2 -0.039 / seed3 +0.059 / seed4 -0.059 / seed5 -0.270
 -> UP in 2/5; delta range [-0.270,+0.112], mean -0.039  (undirected drift)
```

**Pairing correctness (RUN, `dbg_pair.py`, seed 3):** across **69 division events**, each daughter's trait vs its *recorded lineage parent's* trait: `|child−parent|` max **0.997** (≈3.3σ), mean **0.252** (≈0.85σ, exactly `E|N(0,0.3)|`), **99%** within 3σ. If the mitosis.rs creation-order pairing were wrong, these diffs would smear across the whole trait range (~1.5+); they don't. The trait rides the *same* verified `zip(dividing, new_ids)` pairing study 8 uses for biomass/lineage — get that pairing and the trait genealogy is correct for free. The no-mutation arm's exact-1.500/var-0 result is a second, independent proof the inheritance propagates the founder value without corruption.

### Q3 — Process shape → recommend (RUN)

`CpmEvolution` reuses the dFBA growth body and native division verbatim; the ONLY additions are the `self.vmax` dict, its use in `_fba`, the one-line mutation in the division loop, a deterministic `self.rng`, and the two new observables. **Tick loop (unchanged skeleton + trait hooks):**

1. read shared `glucose` field;
2. per live id: `_new_model` if new + seed `self.vmax[cid]=trait_init` if new; dFBA with **per-cell** `vmax` → biomass → `set_target_volume(cid, grow·biomass)`;
3. `world.step(mcs)`;
4. `new_ids = world.divide_cells(vol_threshold, reset_target)`; reconstruct `dividing` from `vols_before ≥ threshold`; for each `(parent, daughter)` in `zip(dividing, new_ids)`: partition biomass by post-split volume (study 8), **`self.vmax[daughter] = clip(self.vmax[parent] + rng.normal(0,σ))`**, record `lineage`/`generation`;
5. re-derive live ids from `np.unique(snapshot())`; compute radial core/rim `local_glucose` diff, `mean_trait`/`var_trait`, `n_cells`, `max_generation`;
6. return field deltas + observables (`overwrite[...]` on the absolute per-cell/scalar readings, plain additive on the `fields` delta — study 8's contract).

### Q4 — Observables + demonstrating metrics

- **Development:** radial core-vs-rim `local_glucose` (or per-cell growth/biomass rate) vs distance-from-centroid, over time — the metric of Q1. Demonstrating signal: rim−core gap emerges 0.04 → 0.97 (rim/core 1.003 → 1.096) as `n_cells` climbs.
- **Evolution:** `mean_trait` + `var_trait` over time, alongside `n_cells`, `generation`/`max_generation`, `lineage`. Demonstrating signal: `mean_trait` shifts up under selection (4/5 seeds, +0.22) while both controls do not (no-mutation flat at founder; no-selection undirected). Corroborating: variance builds only when mutation is on; the selected populations also reach *more* cells (division-rate selection, not just a relabeling).

### Q5 — Framework + deps + guards (confirmed)

Reuses `CpmGrowthDivision` unchanged → **`cpm`** (viva-cpm; native `divide_cells`, `load_world`, `snapshot`, `cell_volumes`/`cell_coms`) + **`cobra`** (`load_model("textbook")` = `e_coli_core`, dFBA) + **`spatio_flux`** (`DiffusionAdvection` shared field). Imports verified together in the worktree venv. **`importorskip` guards (all three, matching every sibling study):** `cpm`, `spatio_flux`, `cobra`. A lighter cobra-free trait/fitness proxy was considered — but the real dFBA path already delivers a clean signal (§2) and keeps continuity with study 8, so **prefer the real dFBA path**; a proxy is unnecessary.

### Q6 — Honest scope (what is / isn't demonstrated)

- **Development = shared-field-driven core/rim physiological heterogeneity** (stewart2008/flemming2016), NOT morphogenesis, signalling, or a genetic patterning program. The "collective interface" is a measured resource gradient, not a regulated body plan.
- **Evolution = ONE scalar heritable trait (`glucose_vmax`) under resource selection** — heritable variation + selection + a directional mean shift, with clean no-mutation and no-selection controls. NOT genome/regulatory-network evolution, NOT speciation. **kirschner2005 "facilitated variation" (mutating *ports/couplings*, not just parameters) is a NAMED DEFERRAL** (deferrals.md item 7, per-cell interfaces): we mutate a *parameter* of a fixed port, exactly the axis the non-spatial study's reviewer said would be needed to move "from pattern to phenomenon."
- This is a **toy evo-devo**: plausible, hand-tuned constants (toy-real per constants-ledger/units-and-timescales), one run window, one modality (chemical). It is, however, a strict *upgrade* over the non-spatial study 9: real heritable variation and real fitness-based selection (differential division on a shared field) replace that study's empty `VariationProc.update()` and fixed-constant `k·viability·fitness` ODE.

### Q7 — Gotchas (each RUN-confirmed)

1. **Config float-override of `0.0` is silently DROPPED (bigraph-schema falsy-scalar trap).** Setting `mut_sigma: 0.0` in the composite state did NOT override the schema default 0.2 (config echo showed `mut_sigma=0.2`), so a "no-mutation" arm built that way *secretly mutates*. **Implement the no-mutation control as a BOOLEAN flag** (`mutation_off: True`) — booleans set to `True` (like `fitness_neutral`) ARE honored, and `seed`/`trait_init` overrides work. This bit once; the plan must not gate any control on overriding a float to zero.
2. **The base process hardcodes the CPM `potts` seed to 1.** Multi-seed requires threading `seed` into the `load_world` spec (the prototype rebuilds the world with `int(config["seed"])`) AND into the mutation RNG. Without it every "seed" shares one Metropolis trajectory. Follow the multi-seed convention (`tests/test_cellcell_multiseed.py`): read `seed` from config, sweep 1–5, assert the qualitative claim per seed, report the range.
3. **Trait-inheritance pairing** — get `zip(dividing, new_ids)` right (study 8's mitosis.rs creation-order reconstruction). Verified correct here (Q2, 99% within 3σ); a wrong pairing scrambles the trait genealogy invisibly (no crash) — the `|child−parent|` bound is the cheap guard test.
4. **Crowding bound (study 8).** The colony saturates its own footprint by ~gen 4–6; the 45-tick run reached 24–70 cells on 60×60 (near lattice saturation). Selection is demonstrable *within* this window but modest and stochastic (one seed reversed). Report the multi-seed *fraction*, not a single-seed headline. More generations need a larger grid / leaner field — which trades against the crowding that itself drives the heterogeneity.
5. **Selection couples to crowding** (corroborating but must be stated): selected populations reach more cells (higher `vmax` → faster division → bigger colony), so the trait shift and the population-size difference are the *same* selection acting through division rate — legitimate, but the claim should say "selection through differential division on the shared field," not imply an independent fitness axis.

---

## 3. Carried-over constraints (hardened conventions, still binding)

- **Worktree discipline:** all work in `<worktree>` (`~/code/meta-modelers-guide--cpm-multicellular`); `PYTHONPATH` prepended; venv interpreter at `<repo>/.venv/bin/python`. This map is the only file written; the prototype is scratch, NOT committed.
- **Full import-path process addresses:** field process is `local:!spatio_flux.processes.diffusion_advection.DiffusionAdvection`; in-repo processes register via `build_core()` (`register_workspace_processes`) and resolve as `local:<ClassName>` (`local:CpmEvolution`). A new class must be re-exported from `meta_modelers_guide/cpm/__init__.py` for the scan to find it.
- **Shared-grid contract:** arrays `(ny,nx)`; CPM dims == spatio-flux `n_bins` == 60×60; `snapshot()` flat `x+y·nx` → reshape `(ny,nx)`; square cells.
- **dFBA path unchanged:** `load_model("textbook")`, MM-limited `EX_glc__D_e.lower_bound` each tick (now `vmax` = the per-cell trait), `EX_o2_e.lower_bound = -oxygen_vmax` (15) forcing acetate overflow, read `sol.fluxes` only when `sol.status == "optimal"`, **one cobra model per cell** (never shared — bound leakage).
- **`overwrite[...]` on absolute observables** (`mean_trait`, `var_trait`, `n_cells`, `max_generation`, per-cell maps); plain additive only on the genuine `fields` spatial delta.
- **Runtime mutation surface:** only `set_target_volume`, `set_contact`, `set_cell_type`, `set_length_constraint`, `set_external_potential`, `remove_cells`, `divide_cells`. `lambda_volume`/`temperature`/seed are init-only → seed must be set at world construction (Gotcha 2).
- **Constants are toy-real** (constants-ledger.md): `glucose_vmax` 1.5 is the study-8 regime (deliberately detuned from 10 for a legible staircase); the trait now *varies* around a founder value, so `glucose_vmax` becomes the evolving quantity rather than a fixed knob. `box_volume_L` 0.3, `grow_per_biomass` 40, `vol_threshold` 80, `reset_target` 40, `mcs` 3, T 11 carried from study 8. Ticks/pixels are model units, dimensionally self-consistent but uncalibrated (units-and-timescales.md).
- **Multi-seed is the acceptance shape** for the evolution headline (deferrals.md "Not deferred"): report the mean-trait shift as a 1–5 seed fraction + range, never one seed.

---

## 4. Open risks / decisions for the plan

1. **Selection legibility inside the crowding-bounded window.** The shift is real but modest and stochastic: mean +0.22 with **4/5** seeds up and one seed reversing, over ~4–6 generations before the lattice saturates. **Decide:** (i) accept the honest multi-seed framing ("up in ≥4/5 seeds; 0/5 no-mutation; undirected no-selection") as the claim — recommended, it is defensible and matches the convention; and/or (ii) sharpen by widening the grid (80×80/100×100) and/or lengthening the run for more generations, and/or raising σ — each buys signal but pushes into heavier crowding and longer runtimes. Do NOT chase a single flattering seed. Budget a short tuning pass on (grid, σ, run length) to land ≥4/5 robustly, then freeze.
2. **Two config/seed gotchas that will silently invalidate the controls (Q7.1–2).** The no-mutation control MUST be a boolean flag, never `mut_sigma=0.0` (silently dropped → the control secretly mutates and *looks like weak selection*, +0.10). And `seed` must be threaded into both the `load_world` potts spec and the mutation RNG or the "5 seeds" are one trajectory. Both are RUN-confirmed traps; bake them into the process design and assert the config echo in a test.
3. **Development gradient is shallow at `vmax` 1.5, and selection is entangled with crowding.** The core/rim glucose ratio only reaches ~1.10 (weak absolute depletion — study 8's ~3% field dip); the heterogeneity is monotone and emergent but visually subtle, and a leaner/higher-`vmax` field sharpens it *and* accelerates the crowding that bounds the evolution window — the two halves pull on the same knob. **Decide** a single regime that keeps the radial gradient legible AND leaves ~4–6 clean generations for selection, or split into two composites (a development-tuned and an evolution-tuned run) if one regime can't serve both. Also state plainly that the trait shift and the larger selected colonies are one mechanism (selection through differential division), not two independent findings.

Lesser: reuse study 8's `{a:1,b:1,j:14}` contact + T 11 for coherent daughters; per-cell trait needs no native support (pure process-side bookkeeping, like lineage); a per-cell-trait heatmap (color the colony by `vmax`) is the natural viz for both halves — the fed rim carrying the higher-trait descendants.
