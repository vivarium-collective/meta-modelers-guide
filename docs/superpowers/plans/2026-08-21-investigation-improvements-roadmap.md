# Investigation improvements — roadmap (from Fable's review)

**Date:** 2026-08-21
**Source:** `scratchpad/fable-investigation-review.md` (Fable's scientific + aesthetic audit against `main.tex`).
**Scope:** all four review tracks, approved by the user. Sequenced into phases so earlier work (bug fixes, shared viz contract, biology-first conventions) feeds the later retrofit and new studies.
**Investigation:** `the-cellular-interface-multicellular` — studies 2/3/4/8 merged; study 6 in progress (branch `study6-biomolecular-complementarity`, code done, study.yaml held); studies 1/5/7/9 planned.

Cite the paper by **section title + quoted phrase**, never figure number alone (figure numbers drifted: Fig 3 = orchestration; **cell–cell coupling has no figure** in current main.tex).

---

## Phase 1 — Foundation & correctness (branch `improve-phase1-foundation`, off current main)

The quick, high-leverage fixes + the shared contracts the retrofit will build on.

- **P1-a. Division state partitioning + lineage** (real fidelity bug). `meta_modelers_guide/cpm/growth_division.py` (~L240–251): daughters' biomass is RESET, not partitioned — Fig 10b: division "partitions state variables such as DNA and biomass." Fix: split the parent's tracked biomass across daughters (proportional to daughter volumes). Keep `divide_cells`' returned ids to record a **genealogy** (founder → generation). Update `growth-and-division-spatial/study.yaml` "mass-conserved" language to cover biological state too; promote the 8→13→16 desync to a finding ("coordination and divergence" via shared-field coupling). Update tests.
- **P1-b. Figure-citation + staleness sweep.** Fix "Fig 3 viability negotiation" → cite the section (`§Cell–cell coupling`, no figure) across spec + all study.yamls + findings. Remove sibling-counting / "only built study" prose from every study.yaml (investigation.yaml owns scope). Add a **lint rule** (`scripts/lint-workspace.py`) flagging: (1) `only built study`/`remain unbuilt`-style sibling counting in study.yaml; (2) bare "Fig N" citations without a section-title anchor.
- **P1-c. Shared viz-style contract.** Refactor `meta_modelers_guide/cpm/viz.py` (~950 lines, 4 bespoke renderers, key-sniffing dispatch) onto a small contract: translucent **footprint fills** + contour; a **Δ-from-t0 field panel** policy; a single **COM accent**; an **event-marker helper** (generalize disintegration's `add_vline`); a **lineage color** scheme (founder hue, per-generation shade, no 6-color recycle); one **title scheme** (pattern name + shared `t`). Register renderers explicitly (no `if "n_cells" in metrics`). All existing viz tests stay green.
- **P1-d. Closed mass-balance standard control.** A reusable check (initial + sources − sinks == final, per species) for field studies — the paper's conservation-law demand + the flagship's own unmet next-step. Write once; the retrofit runs it everywhere.

Ships as one or two PRs. Merge before Phase 3.

## Phase 2 — Study 6 as the exemplar (branch `study6-biomolecular-complementarity`, rebased onto Phase-1 main)

Finish the held study-6 Task 7 on the NEW bar — the first study authored biology-first with paper detail + the viz contract.

- Rebase study 6 onto Phase-1 main (resolve the trivial investigation.yaml overlap).
- Author `biomolecular-complementarity-spatial/study.yaml` biology-first: aim at the paper's **stated** question ("which patterns of complementarity give rise to interfaces that behave as functional, regulatable boundaries, and which produce transient or unregulated aggregates") — the CH study should show a condensate doing **interface work** (selectively concentrating/excluding a species), not just spinodal decomposition. Tie sorting to "which interface variables must align for coupling" (banani2017; not just Steinberg). Cite the paper. Use the viz contract (footprint fills, event markers). Add a calibration band + a control.
- Land study 6 PR.

## Phase 3 — Retrofit merged studies 2/3/4/8 (per-study branches off Phase-1 main)

Apply the new bar to the shipped studies. Per study: biology-first re-voice using Part A quotes + real citations; demote the "two independently-built simulators" refrain to one sentence; add a "what this does NOT demonstrate" paragraph to investigation.yaml owning the monolithic-coupling-process divergence.

- **Cross-cutting: the relational-molecule arc.** Reframe `cell-cell-coupling` around the paper's closing line (acetate = waste to secretor, food to consumer; cite morris2013); make `disintegration`'s stressor **be acetate-as-toxin** → one molecule as waste/nutrient/toxin across three studies; debris deposits lysate mass back to a field.
- **cell-environment-coupling (flagship):** add the O2-uncapped control (overflow claim → experiment); niche-construction citation (odling1996); downgrade "sense/act" → "sense/metabolize/secrete" or build the chemotaxis variant; run the closed mass-balance control.
- **cell-cell-coupling:** add a viable-biomass floor + test whether the loser is pushed out (or retitle away from "competitive exclusion"); stop before lattice saturation or report the 97.5%-occupancy caveat; surface a mechanical variable (shared contact-boundary length); secretor-knockout necessity control; fix `control:` labels; add the compete **metrics panel** (plot the 3.69× margin).
- **disintegration:** cite the phenomenological→emergent viability grading; pilot the mechanistic trigger already in `cell_field.py` (FBA maintenance infeasibility); assert `shed_particles == vacated_pixels`; stop leaning on "deterministic" (BrownianMovement is unseeded); add the moving **viability isoline** to the GIF.
- **growth-and-division:** (bug fixed in P1-a) — record the lineage tree; a longer/leaner-field run so nutrient limitation actually shapes the staircase.
- **GIF fixes** (P1-c contract applied): fix `cellcell-compete` (fills, Δ-panel, cadence-1, metrics panel) and `growth-division` (lineage colors, tightened scale/Δ-panel, event markers).
- **Rigor pass:** 5-seed replicate ranges beside headline numbers; a units/timescale sheet (tick, pixel, box_volume mapping); ≥1 dimensionless literature anchor per study (overflow ratio; state the real ~2× acetate/glucose D ratio vs the used 37.5×).

## Phase 4 — Interface-substitutability flagship variant (the #1 science rec)

Demonstrate the paper's central thesis (§2: "the interface itself … the object of comparison"). Swap `CpmCellField`'s dFBA for a simple **Michaelis–Menten uptake+yield** mechanism behind the **identical ports**; run both; compare interface-level observables. New mechanism class + variant entry + a comparison study section.

## Phase 5 — Pipeline hardening (inherited by studies 1/5/7/9)

- Calibration-bands + literature-citation convention wired to `viva-cite-bands`; require ≥1 banded primary test per study (or an explicit why-not).
- Multi-seed robustness stage before `confidence: Accepted`.
- Shared **constants ledger** (a table of per-study regimes + rationales: `grow_per_biomass`, `oxygen_vmax`, `glucose_vmax`, D-ratios).
- Deferral tracking: dropped spec commitments (chemotaxis, mechanical ports) land in a follow-ups list at deferral time.
- Control taxonomy defined once; four-modality gap (chemical/mechanical/electrical/thermal) named in investigation.yaml using the paper's port vocabulary.
- Then build studies 5 (`molecular-interfaces`), 7 (`autopoiesis` — vesicle negative control), 9 (`development-and-evolution`) on the hardened bar.

---

## Sequencing

P1 → P2 (rebase onto P1) → P3 (per-study, off P1) → P4 → P5. P1-a/b/d are quick correctness wins; P1-c (viz contract) is the largest P1 item and gates the GIF fixes in P2/P3. Each phase lands via PR(s); user approves every merge.
