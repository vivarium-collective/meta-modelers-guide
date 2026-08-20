# Realigning the investigation to the paper's sections, figures, and narrative

**Date:** 2026-08-20
**Status:** Approved design (brainstorming complete) → next: implementation plan (writing-plans)
**Source paper:** `~/Desktop/Meta_Modelers_Guide/main.tex` — *A meta-modeler's guide to the cellular interface and its composition patterns* (Agmon)

## Problem

The `draft-to-living-cell` investigation drifted from the paper it claims to execute:

1. **Figure numbering is wrong.** The investigation's centerpiece "Fig 6 = one metabolism
   interface, three mechanisms" does not exist in the paper. The paper's **Fig 6 is
   *Disintegration***. The investigation elevated *substitutability* — a framework-section
   point (paper lines 223–225: "different mechanisms may realize the same externally
   observable relation") — into a fabricated "Fig 6" thesis.
2. **The paper's framework material is ignored.** Fig 1 (overview), Fig 2
   (`composition_framework` — the actual **schema**: paths/types/values, stores, ports/wires,
   composite), Fig 3 (`orchestration` — multi-timescale, workflow DAG, event rewrites), and
   **Table 1** (the formal vocabulary incl. **R_L process implementation**, which is the real
   "compile" concept) are absent.
3. **Whole paper sections have no study:** Cell–cell coupling, Molecular interfaces,
   Biomolecular complementarity, and Disintegration-as-level-shift are missing or deflated
   into a "gallery."
4. **The compiler/laws apparatus over-leads.** The "5 laws / impostor CompileError" framing
   crowds out the paper's actual thesis (interfaces as biological hypotheses; viability &
   minimal agency; composition as ongoing practice).

## Decisions (locked with the user)

- **9 studies, one per paper pattern-section**, splitting the last section into
  growth/division vs development/evolution.
- **Rebuild the `draft-to-living-cell` investigation in place**, salvaging working code
  (COBRApy FBA, kinetic metabolism, division rewrite, ATP-synthase, nested place graph).
- **Keep the full compiler + 5-laws apparatus prominent**, re-mapped onto the new sections.
- **Framework material (Figs 1–3, Table 1) = investigation-level primer**, not a study.
- **`the-living-atlas` whole-cell** → retired as a standalone study; preserved as an
  **investigation-level synthesis/capstone** that composes several patterns into one running cell.
- **`development-and-evolution`** → kept as **explicitly-caveated pattern demonstrations**,
  consistent with the paper's own hedge (line 580: "an open and substantial challenge").

## Narrative reframe (investigation level)

Study order follows the paper's real arc — zoom-out → break-down → build-back-up →
extend-across-time:

> cellular interface → couple outward (environment, other cells) → **break down**
> (disintegration → drop to molecules) → **build back up** (molecular interfaces →
> complementarity → autopoiesis) → **extend across time** (division → development → evolution)

**Main claim (re-anchored to the paper):** a cellular interface is simultaneously a modeling
choice and a *testable biological hypothesis about which interactions matter*; composition is
an ongoing practice — connect where assumptions hold, **cut the model open at the interface
when they fail**, coarse-grain when organization re-emerges — and the interface is the locus
where chemical dynamics become organized as a self-maintaining, adaptive agent.
**Viability bounds & minimal agency are the throughline.**

The **contract(draft) → compile → executable** apparatus operationalizes exactly what the
paper's Discussion (line 633) and Table 1's **R_L (process implementation)** already name: a
semantic layer compiled into the executable models that realize it. Framework material
(Figs 1–3, Table 1) is the investigation-level primer every study's contract references.

## The 9 studies

Section-faithful slugs, in paper order. Each study is authored as a typed **contract (draft)**
and **compiled** (one conforming mechanism installed per draft) into an **executable**, with
interface preservation checked.

| # | Study (slug) | Paper §/Fig | Contract (draft ports) | Compiled mechanism(s) → executable demonstrates |
|---|---|---|---|---|
| 1 | `cellular-interface` | Cellular interface / Fig 4 | chemical mol·s⁻¹, mechanical N, electrical C·s⁻¹, thermal J·s⁻¹ + growth, shape, objective, **viability**; chem/mech subports | Bounded goal-directed cell; ports carry values, viability stays in-band. **Home of Law 1 conformance + impostor** (breaks *this* base contract). |
| 2 | `cell-environment-coupling` | Cell–env / Fig 5 | cell interface + shared env store + env processes (diffusion) | Sense/act loop over a real diffusing field; **niche construction** (cell reshapes the gradient it depends on). |
| 3 | `cell-cell-coupling` | Cell–cell / *(shared env; biofilm Fig 10c,d)* | two cell interfaces + shared env + adhesion/signaling ports | **NEW.** Viability *negotiation*: competition (depletion pushes a neighbor out of bounds) vs cross-feeding (cooperation stabilizes both). |
| 4 | `disintegration` | Disintegration / Fig 6 | cell-metabolism exchange w/ viability gate ↔ molecular reaction network | **Level-of-description shift**: cross viability bounds → cell process "cuts open" into a molecular network; inverse coarse-grains back. **New home for the 3 metabolisms** (coarse = cell-level, FBA = resolved molecular network, kinetic = intermediate grain) — literally Fig 6 panel b. |
| 5 | `molecular-interfaces` | Molecular interfaces / Fig 7 | chemical/electrical/mechanical/thermal channels + substrate/cofactor/catalyst/product | F1Fo ATP-synthase: PMF (electrical/thermal) in → ATP (chemical) out, honoring all 4 channels. |
| 6 | `biomolecular-complementarity` | Complementarity / Fig 8 | molecules w/ binding sites/conformation + complementarity gating; nested place graph | **Selectivity**: only complementary partners react; assembly into the six-level nested composite (+ optional condensate/phase readout). |
| 7 | `autopoiesis` | Composition of the interface / Fig 9 | metabolism + containment + replication, mutually wired; viability emerges | Closed loop sustains itself; break a coupling → interface loses meaning. **Second home of grain-swap** (coarse/self-organized/molecular). Honest "pattern, not validated autopoiesis" caveat. |
| 8 | `growth-and-division` | Growth/division / Fig 10a,b | growing stores + division rewrite | Grow → DNA threshold → one node becomes two, mass-conserved, daughters re-couple to shared env. |
| 9 | `development-and-evolution` | Dev/evolution / Fig 10c–f | biofilm-nesting rewrite + port-addition variation + viability selection | Cells nest into a collective composite w/ its own interface (development); a new port expands interaction, selected by viability (evolution). **Explicit caveat**: pattern demonstrations, not validated results. |

**Key realignment:** the fabricated "Fig 6 = metabolism" showcase dissolves. The real COBRApy
FBA finds its *correct* paper home as the **resolved molecular network** in Disintegration's
Fig-6 grain-swap — a better fit than it ever had.

## Where the 5 laws live (kept prominent)

- **Law 1 Conformance + impostor/CompileError** → `cellular-interface` (impostor breaks the
  base cell contract — paper-faithful, vs the old fabricated metabolism figure).
- **Law 2 Interface preservation / Law 3 Executability** → every study (draft render vs
  executable dynamics; inert-draft control).
- **Law 4 Handler independence (grain-swap)** → `disintegration` (Fig 6) + `autopoiesis`
  (Fig 9) — the two places the paper *actually* argues one interface / many grains.
- **Law 2′ Rewrite preservation** → `growth-and-division` + `development-and-evolution`.

## Migration / salvage plan

| Current study | Becomes |
|---|---|
| `typed-interface` | splits → `cellular-interface` (Fig 4) + `cell-environment-coupling` (Fig 5) |
| `one-interface-three-mechanisms` | 3 metabolisms → `disintegration` + `autopoiesis`; impostor → `cellular-interface` |
| `the-nested-cell` | splits → `molecular-interfaces` (Fig 7) + `biomolecular-complementarity` (Fig 8) |
| `divide` | → `growth-and-division` (already strong; largely reused) |
| `the-living-atlas` | thermal-shock/disintegration → `disintegration`; whole-cell → **investigation-level capstone**, not a 10th study |
| `gallery` | dissolves; deflated Fig 9 / Fig 10-2 / Fig 10-3 promoted into `autopoiesis` and `development-and-evolution`; a coverage note stays investigation-level |

**Net new code:** `cell-cell-coupling` (study 3) is genuinely new. `disintegration` needs the
level-shift (cell-metabolism ↔ molecular-network rewrite) genuinely built, not scripted.

## Mechanics

- Precondition: workbench running. `workspace.yaml` has `server.enabled: false` → run
  `/viva-workbench start` first.
- `/viva-study` — create the 9 studies, retire/rename the 6 old ones.
- `/viva-investigation` — investigation overview, study order, status, capstone synthesis.
- `/viva-viz` — regenerate figures where the mechanism changed.
- `/viva-report` — reviewer-readiness audit + regenerate dashboard/report before hand-off.
- All study writes go through the skills (canonicalization + provenance), not direct YAML edits.

## Out of scope

- Calibrating handlers to fitted parameters (handlers stay "toy-real"; caveat preserved).
- New process-bigraph / viva-compiler core features — this is a workspace-content realignment.
- Higher-organization patterns beyond the paper (tissues/organs) — paper defers these too.

## Testing

- Each study keeps its `draft-is-inert` control (Law 3) and a draft-vs-executable interface
  check (Law 2), enforced in `tests/`.
- `cellular-interface` retains the impostor → `CompileError` test (Law 1).
- `disintegration` + `autopoiesis` retain handler-independence tests (Law 4) for the grain-swap.
- `growth-and-division` + `development-and-evolution` retain rewrite-preservation tests (Law 2′).
- COBRApy-dependent tests stay guarded to skip when `cobra` is absent (as in commit #32).
