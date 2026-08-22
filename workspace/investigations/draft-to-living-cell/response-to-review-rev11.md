# Response to peer review — *From Draft to Living Cell* (rev. 11)

We thank the reviewer for an unusually careful reading. We accept the core diagnosis: the
compositional-methodology contribution is real, and the biological-claim layer was over-leveled
relative to its evidence — riding on self-authored gates, tuned agreement, and under-powered
statistics. This revision **re-levels every claim to match the evidence** and schedules the
experiments that would raise it. We adopt the reviewer's own closing framing as the honest headline:
the nine patterns can each be *expressed, run, and consequence-tested* as compositions of
independently-built simulators behind typed interfaces, with single-variable controls — a
well-engineered draft, not a validated cell.

Two tiers of response below. **Now (this revision):** claim re-leveling + cheap real fixes.
**Next step (scheduled):** the compute experiments, each named at the point where its claim currently
stops. Nothing is left implied; where an experiment is pending, the *language* no longer claims its
result.

---

## Major issues

### M1 — Self-referential validation; no external target
**Now.** We separate the two kinds of gate explicitly. Every per-study `pass_if` is tagged
`kind: regression_pin` (a threshold set after the run — a rerun-guard, honestly labeled) vs
`kind: acceptance_criterion` (a directional prior stated before the run). The investigation-level
`acceptance_criteria` block — previously empty — is populated with **pre-stated priors** (overflow
secretion under an O₂ cap; growth under nutrients; knockout-below-control maintenance; selection
drift; and an explicit *unmet* substitutability criterion) plus **order-of-magnitude external
anchors** (acetate yield ~0.3–0.5 mol/mol; glucose uptake ~10 mmol/gDW/hr; diffusivity ratio
~1.5–2×), each flagged as an anchor, not a calibration target. The `Accepted` / `needs_calibration`
contradiction is resolved (see minor 2).

### M2 — SWAP is a fit, not a finding
**Now.** Every SWAP claim across the investigation and the affected studies is relabeled **surrogate
calibration**: a tuned Michaelis-Menten twin (four free parameters) reproduces the interface
observables within ~10% *on the condition it was tuned on*. We state the degrees of freedom (four
knobs / ~four observables) and no longer call it "substitutability demonstrated" or "the
equivalence-class claim made executable." The colony-level ~0.2% volume agreement is now flagged as
a **finite-lattice saturation artifact** (~97.5% occupancy — both mechanisms hit the same ceiling),
not interface agreement. The finished 3rd swap (interface-realization) already sweeps the operating
range chem∈[0.2, 2.5] rather than a single point (max ~10.5% across the range, byte-identical ports).
**Done (rev-12b, measured).** The held-out battery is run with the MM params frozen. Single cell:
mechanism-independent WITHIN the calibrated glucose-limited/fixed-O₂ regime (held-out ~13% on a
different glucose field and a 2× run), but ~74% divergence on a held-out O₂ cap the lumped box has no
oxygen variable for — surrogate calibration across the O₂ axis, mechanism-independence within it.
Colony pre-saturation: growth/competition observables agree ~9%, but the ~0.2% acetate match was a
lattice-saturation artifact — pre-saturation the acetate diverges ~68%. DoF reported (single cell
4/4 exactly determined; colony 2 free/6 over-constrained, and the one parameter controls exactly the
acetate that fails). `tests/test_substitutability_heldout.py`, `tests/test_cellcell_presaturation.py`.

### M3 — Evolution "CAUSED by selection" not supported at n=5
**Now.** Softened to **"consistent with selection"** everywhere; the dev-evo study records that n=5
(4/5 vs 2/5, Fisher p ≈ 0.5) is under-powered, that most selection-ON deltas fall within a plausible
drift envelope, and that the committed gate currently evaluates flagship seed 3.
**Done (rev-12b, measured — claim upgraded).** A 30-seed ensemble per arm: selection-ON mean delta
+0.233 (up 22/30) vs no-selection −0.026 (up 13/30); Mann–Whitney U p = 5.3e-4, rank-biserial
r = +0.52, and a Wilcoxon drift-null p = 1.2e-5 (the shift is distinguishable from neutral drift).
The gate is re-based on the ensemble statistic (`gate_class: acceptance_criterion`), seed 3 kept only
as a regression pin. The effect is significant but medium — about a third of selection-ON seeds still
drift down, stated as such. `scripts/run_dev_evo_ensemble.py`, `tests/test_dev_evo_ensemble.py`.

### M4 — EMERGE/autopoiesis causally circular
**Now.** Reframed as **"authored operational closure, consequence-tested."** We state plainly that
closure-dependence is hand-coded via a global `binary_fill_holes` observer, not emergent from local
physics, and that the knockout and puncture results follow from that construction. The value claimed
is narrower and true: the criterion is implemented and its consequences verified.
**Next step.** A mechanistically-local loop (production gated on an interior-retained precursor whose
concentration collapses when the membrane leaks), which would make the puncture a real prediction.

### M5 — Disintegration mass conservation (68 shed vs 56 px)
**Now.** The claim "genuine spatial dissolution, not scripted" is corrected: the trigger timing is
simulation-derived, but the resorption ramp (`resorb_per_tick = 6.0`) is **scripted**. The study now
records the unresolved discrepancy — 68 shed particles exceed the 56-px area at release — and puts
the "shed material, not deleted mass" claim **on hold** until a ledger closes it. BrownianMovement is
now seeded (see M6).
**Done (rev-12b, measured — real bug found and fixed).** The CPM→particle mass ledger exposed a
genuine double-count: 6 pixels were shed twice (vacated, re-occupied by CPM Metropolis fluctuation as
the footprint drifts, then vacated again). The weak bound `shed ≤ unique_vacated` (68 ≤ 69) *masked*
it — only `shed == distinct_pixels` caught it. Fixed with an already-shed guard: now 63 particles at
63 distinct pixels ≤ 69 unique vacated. The ledger closes and "shed material, not deleted mass" is
restored *with* the honest explanation — the cell traverses 69 distinct pixels over its released
lifetime (drift), not the 56 it holds at the release instant. `tests/test_disintegration_ledger.py`.

### M6 — Reproducibility / hygiene
**Now.** (a) **BrownianMovement is seeded** (`seed: 1`) — the debris scatter is now deterministic.
(b) GrayScott/Protocell seed handling addressed (wired through, or the baked-IC behavior documented
where the composite pins it). (d) Expected-fail controls (`draft-is-inert`) are tagged
`expected_result: fail` so they are not counted as passes; the neutral-J sorting regime sweep and
`requires_simulation: none` diagnostics are marked as non-committed / diagnostic rather than tallied
as committed pytests.
**Next step.** (c) A config-roundtrip test per composite that fails loudly on a dropped key (the
`mut_sigma: 0.0` silent-drop class of bug), and elevating that `bigraph_schema` behavior in the docs.

### M7 — Biophysics vs vocabulary
**Now.** (a) Cross-feeding: the 37.5× acetate/glucose diffusion ratio is stated honestly as a
**legibility choice** (~20× the physical ~1.5–2× ratio), not "directionally defensible." (b)
Competition: "competitive exclusion / Gause" is dropped for two single non-dividing cells →
**"resource preemption between two cells,"** with a note that population-level exclusion needs
dividing populations and that the ~97.5%-lattice swell is an artifact. (c) A **units-and-time block**
per study states that a tick is dimensionless model time and quantities are dimensionless model
units; unearned "mM" labels are de-decorated.
**Next step.** A realistic-diffusivity run, a dividing-population competition (study-8 machinery), one
source/sink steady-state regime, and a cadence-halving convergence check for the flagship.

### M8 — Development half single-seed
**Now.** The dev-evo study records that `rim_core_ratio` 1.0→~1.44 is flagship seed 3 only.
**Next step.** Report the ratio across seeds 1–5 with per-cell scatter (paired with the M3 re-run).

---

## Minor issues
1. **Drawdown** — flagship now states **both** ~18% peak-to-trough and ~6% from the initial condition.
2. **Status** — reconciled to one signal: per-study `confidence: Provisional` (gates pass as
   regression pins; acceptance pending calibration), investigation `status: running`, executive
   `verdict_status: needs_calibration`. The report header badge now shows the verdict_status, not a
   green "running."
3. **Expected-fail** — `draft-is-inert` gets `expected_result: fail`; no longer misreadable as a PASS.
4. **Performative honesty** — trimmed repeated "honest / stated plainly / load-bearing"; scope-only
   `partial` findings moved into `limitations` rather than inflating finding counts.
5. **"Turing"** — molecular study now says finite-amplitude, nucleation-driven Gray-Scott patterning
   (not linear-instability Turing sensu stricto); the equal-diffusion conclusion is marked
   regime-specific.
6. **"Thermal channel"** — corrected to "a static, uniform temperature field as an Arrhenius rate
   multiplier (no heat transport, no reaction→heat feedback)"; not "two physical channels compose."
7. **Title/frame** — the arc language and the title are flagged **up front** in the executive as a
   narrative reading, tied to the verdict's "not a quantitatively validated cell."
8. **"Niche construction"** — the flagship now says **"environmental modification"**; the term is
   reserved for development-and-evolution, where a selection feedback exists.
9. **Float-equality gates** — `== x` gates carry a tolerance / `deterministic_pin` note.
10. **Headline band** — the cell-cell study leads with the **2.9–3.7× band** (3.69× on the flagship
    seed), not the single-seed number.
11. **Provenance** — the "metrics figure skipped: too large to inline" case is fixed; package
    version / commit / env-hash capture is scheduled.
12. **Native impostor** — the cellular-interface study gets its own Law-1 impostor instead of
    borrowing another study's.

## Questions for the authors
1. **Were gates pre-stated?** Most were regression pins set after the run — now labeled as such
   (`kind: regression_pin`); the genuine priors are separated as `acceptance_criterion` and listed at
   investigation level. (M1)
2. **68 vs 56 in Disintegration?** Likely re-vacated-pixel double-counting; the claim is on hold
   pending the CPM→particle mass ledger. (M5)
3. **MM swap under a held-out condition / pre-saturation colony?** Not yet run; named as the SWAP
   frontier, and the current result relabeled surrogate calibration. (M2)
4. **Null distribution of `mean_vmax` drift at n≥20?** Scheduled (drift-null + rank test); claim
   softened to "consistent with selection" until then. (M3)
5. **How many config keys are silently dropped?** Unknown pending a per-composite config-roundtrip
   audit (scheduled); the one known case (`mut_sigma: 0.0`) is documented. (M6c)
6. **What is a tick / are the field units real?** A tick is dimensionless model time; the "3.0 mM"
   label was decorative and is de-decorated. (M7c)
7. **Why was BrownianMovement unseeded?** An oversight — now seeded. (M6a)
8. **Equal-diffusion control — truly single-variable?** Recorded honestly in the molecular study;
   the control shares the flagship's initial condition apart from the diffusion coefficients (the
   single varied variable). (Q8)
9. **What could the autopoiesis experiment have discovered?** With the current authored global gate,
   little beyond what the code entails — which is exactly why the claim is reframed as authored
   closure and a local-mechanism version is the next step. (M4)
10. **Flagship trajectory under halved coupling cadence?** Not yet tested; a cadence-halving
    convergence check is scheduled. (M7d)

---

---

## Revised claims register (rev.11 → rev.12b)

Every headline claim, before and after — the after column is the *measured* result, not a promise.

| Claim | BEFORE (rev.11) | AFTER (rev.12b) |
|---|---|---|
| **SWAP / substitutability** | "Substitutability is demonstrated (dFBA vs lumped MM behind the same interface, observables within ~10%) at two levels." | Mechanism-independence **measured against held-out conditions**: holds within the calibrated glucose-limited/fixed-O₂ regime (single cell ~13%, colony growth ~9% pre-saturation); breaks where the lumped box lacks a needed variable (O₂ axis ~74%, acetate trajectory ~68%). Regime-bounded, boundary pinned. DoF reported. |
| **Selection causality** | "Only selection-ON shifts the mean directionally, so the trait shift is CAUSED by selection." (n=5, gate on seed 3) | **Selection drives the shift — measured**: 30-seed ensemble, Mann–Whitney p=5.3e-4, drift-null p=1.2e-5, r=+0.52; gated on the ensemble statistic. Significant but medium (a third of seeds still drift down). |
| **Autopoiesis / EMERGE** | "The membrane is produced AND maintained from the inside — the paper's individual criterion." | **Authored operational closure, consequence-tested**: closure-dependence is a hand-coded global `binary_fill_holes` observer, not emergent-from-local-physics; knockout/puncture follow from that construction. Local-mechanism version (Protocell v2) is a named next build. |
| **Disintegration mass** | "Genuine spatial dissolution, shed material not deleted mass" (68 shed). | **Ledger closes after fixing a real double-count**: 6 pixels were shed twice; corrected to 63 at 63 distinct pixels ≤ 69 unique vacated. Claim restored *with* the drift explanation. |
| **Competitive exclusion** | "Drives asymmetric growth toward competitive exclusion (3.69× margin)." | "**Resource preemption** between two non-dividing cells (2.9–3.7× across seeds); population-level exclusion needs dividing populations. The ~97.5%-lattice swell is an artifact." |
| **Cross-feed geometry** | "37.5× acetate/glucose diffusion ratio is directionally defensible." | "A **legibility choice** (~20× the physical ~1.5–2× ratio), stated as such; a 2:1 realistic-diffusivity run is queued." |
| **Flagship niche** | "Depletes footprint glucose up to ~18% — niche construction." | "**Environmental modification** (both numbers: ~18% peak-to-trough, ~6% from the initial condition); 'niche construction' reserved for dev-evo where a selection feedback exists." |
| **Validation gates** | "57/57 pass; confidence Accepted." | "Gates split **regression_pin vs acceptance_criterion**; investigation `acceptance_criteria` populated with pre-stated priors + external anchors; studies `Provisional`; counts split committed/narrated/expected-fail; config-consumption audit clean across 52 composites." |
| **Verdict line** | "The pattern set is complete and the central claim holds in executable form." | "The patterns compose and run with single-variable controls; SWAP holds **within its regime** (boundary measured), selection is **significant** (p=5.3e-4), EMERGE is authored-closure. A well-engineered draft, demonstrably; a validated cell, not yet." |

## Prioritized checklist — could it change the headline verdict?

| Item | Status | Could change the verdict? |
|---|---|---|
| M1 gate-class split + pre-stated ACs + anchors | ✅ done | Changes what "passed" means everywhere |
| M6 config-consumption audit | ✅ done — **clean** (0 dropped keys / 52 composites, check proven sensitive) | Yes — a dropped load-bearing key would have forced re-runs; none found |
| M3 30-seed selection + rank test + drift-null | ✅ done — **significant** | Yes — and it *upgraded* the claim |
| M2 held-out SWAP + pre-saturation colony | ✅ done — **regime-bounded** | Yes — re-leveled SWAP to condition-local, boundary measured |
| M5 CPM→particle ledger | ✅ done — **bug found + fixed** | Study-level: identity claim now rests on a closed ledger |
| M4 autopoiesis reframe | ✅ done (reframe) | EMERGE weakest of three verbs, stated |
| M7/M8 units, band, niche, thermal, dev band | ✅ done (re-level) | Study-level |

## Named next builds (concrete, not vaporware)
- **Protocell v2** — emergent closure via an interior precursor `p` (production `k_prod·φ·p`, `p` lost by leakage where the membrane is open), making the puncture a real self-heal prediction rather than a restatement. Ship v1-relabeled + the v2 result whichever way it falls.
- **M7 remainder** — cross-feed at a 2:1 realistic diffusivity (longer horizon), dividing-population competition (`cellcell-compete-div` + viability floor, to earn or drop "competitive exclusion"), one source/sink steady-state regime + a cadence-halving convergence check.

---

*The reviewer's test of success — that the revision contain at least one gate that could have failed and
is reported honestly whichever way it fell — is met several times over, not as a promise but as run
results: the SWAP held-out battery divulged a ~74% O₂-axis divergence and a ~68% pre-saturation acetate
divergence; the selection ensemble could have come back null and instead cleared p=5.3e-4; and the mass
ledger found and fixed a real double-count the weaker bound had masked. Naming a weakness is not
neutralizing it — so we ran the experiments and let them speak.*
