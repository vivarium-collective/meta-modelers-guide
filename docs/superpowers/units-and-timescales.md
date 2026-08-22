# Units and timescales — `the-cellular-interface-multicellular`

Toy-real is a legitimate modeling stance; **dimensionally uncharacterized** toy-real is a
footgun, because it invites the first skeptical question every time (Part B-0.3 / E-10 of the
Fable review). This sheet answers that question up front: what a tick is, what a lattice pixel
is, how cobra's fluxes become field deltas, and what the diffusion coefficients mean. The
honest summary is that the dynamics are dimensionally *self-consistent within each run* but not
*calibrated to physical units* — the numbers are relative, not SI.

## What a "tick" is

**Unmapped model time.** A process-bigraph tick is one `update(state, interval)` call; nothing
in the investigation maps `interval` to seconds, minutes, or hours. Two things ride on it:

- In the dFBA/MM metabolism (`cell_field.py`, `colony_field.py`), the FBA solve returns fluxes
  in **mmol·gDW⁻¹·hr⁻¹**, and the code multiplies by `interval` as if it were an elapsed time in
  **hours** (`d_biomass = mu · biomass · interval`; `d_glc = glc_flux · biomass · interval /
  box_volume_L`). So one tick is *treated as* one hour inside the flux arithmetic — but that
  "hour" is a bookkeeping convention that keeps the flux units consistent, not a claim that a
  tick is a wall-clock hour. Run lengths (20, 36 ticks) are chosen for legibility, not to model
  a real cell-cycle duration.
- In the CPM engine, each tick advances `mcs` Monte Carlo sweeps (`mcs` 3 for the metabolic
  studies, 10 for sorting). Monte Carlo steps are the CPM's own dimensionless relaxation clock;
  they do not map to physical time either.

Consequence, stated plainly: every rate, half-life, or "per-tick" number in the studies is in
**model time**. Ratios between them (e.g. how many ticks until the acetate plume reaches the
consumer) are meaningful; their absolute duration is not.

## What a lattice pixel is

**Dimensionless / unmapped physical size.** A CPM cell is a set of lattice pixels on a 60×60
(or 70×70 for sorting) grid. No pixel is assigned a micron size, so a "volume" of 110 px or an
"area" of 56 px is a relative lattice measure, not µm² or fL. Coverage fractions (e.g. the
flagship cell reaching ~3% of a 3600-px lattice, or the competition winner ~97.5%) are the
honest way these are read — as fractions of the finite lattice, which is itself the point in the
competition study (the ~97.5% endpoint is partly a finite-size saturation artifact, not a
biological carrying capacity).

## The `box_volume_L` mapping (flux → field concentration)

This is the one knob that carries the dimensional bridge, so it is worth stating exactly. In
`cell_field.py` / `colony_field.py`:

```
d_glc = glc_flux · biomass · interval / box_volume_L
```

- `glc_flux` — cobra exchange flux, **mmol·gDW⁻¹·hr⁻¹**
- `biomass` — the cell's tracked biomass, treated as **gDW**
- `interval` — the tick, treated as **hr** (see above)
- `box_volume_L` — the effective **liters** of medium the footprint's exchange is diluted into

So `mmol·gDW⁻¹·hr⁻¹ · gDW · hr / L = mmol·L⁻¹` — a **concentration delta** in the field's own
mmol·L⁻¹-equivalent units. `box_volume_L` is therefore the amount→concentration converter: a
smaller box concentrates the same exchange into a larger per-pixel delta. Every metabolic
composite pins it to **0.3** (the code default is 1e-6; each composite overrides it), so the
flux→field conversion is comparable across studies. The field's absolute concentration scale is
thus "mmol·L⁻¹ if you accept box_volume_L = 0.3 L and a tick = 1 hr" — i.e. real *shape*,
uncalibrated *scale*.

## Diffusion coefficients are unitless-relative

The `DiffusionAdvection` coefficients (glucose 0.4, acetate 0.6, or acetate 15.0 in the
crossfeed regime; acetate 4.0 in disintegration; debris `diffusion_rate` 1.0) are **relative
lattice-diffusion rates**, not cm²·s⁻¹. What is meaningful is the *ratio* between species and
between studies:

- glucose 0.4 vs acetate 0.6 in the default field — acetate slightly faster, directionally right.
- the crossfeed regime raises acetate to 15.0 (a **37.5×** D-ratio over glucose) purely so the
  byproduct plume crosses the inter-footprint gap within 20 ticks. This is directionally
  defensible (acetate is the smaller molecule) but ~20× larger than the real aqueous
  acetate/glucose ratio of roughly **2×** (≈1.2e-5 vs 6.7e-6 cm²·s⁻¹). The study owns this in its
  own limitations; it is a legibility choice, not a measured coefficient.

## One-line honesty statement for a skeptic

The spatial dynamics are **dimensionally self-consistent and physically uncalibrated**: fluxes,
biomass, and field concentrations share one internally-coherent unit system (mmol / gDW / hr /
L via `box_volume_L`), lattice pixels and ticks are relative model units with no assigned
physical size or duration, and diffusion coefficients are relative rates whose cross-species and
cross-study *ratios* are the load-bearing quantities. Nothing here is fitted to a named organism,
medium, or measured coefficient — by design, matching `draft-to-living-cell`'s toy-real
convention.
