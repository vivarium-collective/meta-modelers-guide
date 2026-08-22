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
**Next step.** A held-out test — tune on one condition, test on a condition neither mechanism saw
(different field, O₂ cap, run length; a held-out sub-range for the realization swap) — and a
pre-saturation colony comparison. These are named as the frontier before "substitutable" is earned.

### M3 — Evolution "CAUSED by selection" not supported at n=5
**Now.** Softened to **"consistent with selection"** everywhere; the dev-evo study records that n=5
(4/5 vs 2/5, Fisher p ≈ 0.5) is under-powered, that most selection-ON deltas fall within a plausible
drift envelope, and that the committed gate currently evaluates flagship seed 3.
**Next step.** 20–50 seeds/arm, a rank test (selection-ON vs no-selection deltas) against a drift
null, and re-gating on the ensemble statistic rather than seed 3.

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
**Next step.** A CPM→particle mass ledger asserting `n_particles ≤ unique vacated pixels` across the
conversion, reusing the flagship's per-species ledger machinery.

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

*This revision does the re-leveling and the cheap real fixes in full; the scheduled experiments are
tracked as the investigation's named frontier, each attached to the claim it would raise.*
