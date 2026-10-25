"""Fig 9 · growth & division — a *mechanistic* cell cycle: growth-, energy- and
size-GATED division with nucleotide-accounted replication.

The baseline (fig09-rewrite, CellCycleDivision) does a genuine place-graph rewrite
on a `colony: tree[node]` and divides on a fixed clock — verifying the graph
rewrite and exact DNA equipartition (bookkeeping), but NOT biological growth or a
self-sustaining cycle: division happens whether or not the cell grew, and the
duplicated chromosome's DNA appears from nowhere.

This variant keeps the same tree[node] colony rewrite but makes division an
OUTCOME of physiology, on the same lineage structure:

* Each cell carries real state — volume, energy (ATP), a nucleotide precursor
  pool, biomass, and chromosomes (DNA) — and GROWS by taking up a shared, finite
  nutrient with saturating Michaelis–Menten kinetics (demand is allocated across
  cells and can never exceed what is in the environment → a real sink).
* REPLICATION is gated: a cell duplicates its chromosome only once it has grown
  past V_rep AND has the nucleotides and energy for it. The new chromosome's DNA
  is drawn FROM the nucleotide pool (Nuc −= dna, DNA += dna) and costs ATP — so
  total (DNA + nucleotides) is conserved; DNA is not created from nothing.
* DIVISION is gated by a checkpoint: a cell splits ONLY when volume ≥ V_div AND it
  has replicated (2 chromosomes) AND energy ≥ div_cost. On division it partitions
  volume, energy, nucleotides, biomass and chromosomes between two daughters
  (each wired to the shared extracellular nutrient → independent ports) and the
  daughters continue. Starve the cell (nutrient ≈ 0) and the checkpoint is never
  met → division is DELAYED, not fired on a clock.

So 1→2→4 still happens, but only when the cells actually grow; conservation holds
across every rewrite; and nutrient exhaustion or starvation stalls the cycle.

Registered automatically at local:GrowthDivisionColony by build_core.
"""
from __future__ import annotations

import copy

from process_bigraph import Process


def _f(d):
    return {"_type": "float", "_default": d}


def _chrom(dna=1.0):
    return {"_control": "chromosome", "contents": {"dna": dna}}


def _chrom_dna(chrom, default=1.0):
    if "dna" in chrom:
        return chrom["dna"]
    c = chrom.get("contents")
    return c["dna"] if isinstance(c, dict) and "dna" in c else default


def _cell_chromosomes(cell):
    c = cell.get("contents")
    src = c if isinstance(c, dict) else cell
    return [(k, v) for k, v in src.items()
            if not k.startswith("_") and isinstance(v, dict) and v.get("_control") == "chromosome"]


def _cells(colony):
    return [(k, v) for k, v in colony.items()
            if not k.startswith("_") and isinstance(v, dict) and v.get("_control") == "cell"]


def _cell_dna(cell):
    return sum(_chrom_dna(v) for _, v in _cell_chromosomes(cell))


class GrowthDivisionColony(Process):
    """Growth-, energy- and size-gated cell cycle over a colony tree[node], with
    nucleotide-accounted replication and conserving partition at division."""

    config_schema = {
        "vmax": _f(0.6), "km": _f(5.0),            # Michaelis–Menten uptake of shared nutrient
        "grow_vol": _f(0.5), "grow_energy": _f(0.4),
        "grow_biomass": _f(0.3), "grow_nuc": _f(0.3),
        "v_rep": _f(1.4),                          # volume needed to start replication
        "v_div": _f(1.8),                          # volume needed to divide
        "rep_rate": _f(1.0),                       # DNA synthesised per tick while replicating (≤ one chromosome)
        "atp_per_dna": _f(0.1), "div_cost": _f(0.1),
        "capacity": _f(16.0),
    }

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core)
        self._n = 0
        self._divisions = 0

    def inputs(self):
        return {"colony": "tree[node]", "substrate": "concentration"}

    def outputs(self):
        return {
            "colony": "overwrite[tree[node]]",
            "substrate": "concentration",
            "cell_count": "float", "tot_volume": "float", "tot_dna": "float",
            "tot_nucleotides": "float", "tot_biomass": "float", "tot_energy": "float",
            "divisions": "float",
        }

    def _set(self, port, value):
        if not hasattr(self, "_last"):
            self._last = {}
        d = value - self._last.get(port, 0.0)
        self._last[port] = value
        return d

    def update(self, state, interval):
        c = self.config
        colony = copy.deepcopy(state["colony"])
        s_ext = float(state.get("substrate", 0.0))
        cells = _cells(colony)

        # ── growth: allocate the shared, finite nutrient across cells (MM demand) ──
        demands = []
        for _, cell in cells:
            s = max(s_ext, 0.0)
            demands.append(c["vmax"] * s / (c["km"] + s) * interval)
        total_demand = sum(demands)
        scale = 1.0 if total_demand <= s_ext or total_demand == 0 else s_ext / total_demand
        total_uptake = 0.0
        for (_, cell), dmd in zip(cells, demands):
            u = dmd * scale
            total_uptake += u
            cell["volume"] = float(cell.get("volume", 1.0)) + c["grow_vol"] * u
            cell["energy"] = float(cell.get("energy", 1.0)) + c["grow_energy"] * u
            cell["biomass"] = float(cell.get("biomass", 1.0)) + c["grow_biomass"] * u
            cell["nucleotides"] = float(cell.get("nucleotides", 1.0)) + c["grow_nuc"] * u

        # ── replication: gated, DNA drawn FROM the nucleotide pool (conserved) ──
        for _, cell in cells:
            vol = float(cell.get("volume", 1.0))
            chroms = _cell_chromosomes(cell)
            if vol >= c["v_rep"] and len(chroms) == 1:
                base = _chrom_dna(chroms[0][1])
                nuc = float(cell.get("nucleotides", 0.0))
                energy = float(cell.get("energy", 0.0))
                need = min(c["rep_rate"] * interval, base)          # grow the 2nd chromosome up to `base`
                existing2 = cell.get("contents", {}).get("chromosome_1")
                have = _chrom_dna(existing2) if isinstance(existing2, dict) else 0.0
                need = min(need, base - have)
                atp = c["atp_per_dna"] * need
                if need > 0 and nuc >= need and energy >= atp:
                    cell["nucleotides"] = nuc - need            # DNA sourced from precursors
                    cell["energy"] = energy - atp
                    first = cell.get("contents", {}).get("chromosome_0")
                    first_dna = _chrom_dna(first) if isinstance(first, dict) else base
                    cell["contents"] = {"chromosome_0": _chrom(first_dna),
                                        "chromosome_1": _chrom(have + need)}

        # ── division: gated by volume + replication + energy; conserving partition ──
        cap = int(c["capacity"])
        for key, cell in list(_cells(colony)):
            if len(_cells(colony)) >= cap:
                break
            chroms = _cell_chromosomes(cell)
            vol = float(cell.get("volume", 1.0))
            energy = float(cell.get("energy", 0.0))
            replicated = len(chroms) >= 2 and all(_chrom_dna(v) >= _chrom_dna(chroms[0][1]) - 1e-9 for _, v in chroms)
            if vol >= c["v_div"] and replicated and energy >= c["div_cost"]:
                del colony[key]
                gen = int(cell.get("generation", 0)) + 1
                post_energy = (energy - c["div_cost"]) / 2.0        # div cost paid once, then split
                for i in range(2):
                    self._n += 1
                    colony[f"cell_{self._n}"] = {
                        "_control": "cell",
                        "volume": vol / 2.0,
                        "energy": post_energy,
                        "nucleotides": float(cell.get("nucleotides", 0.0)) / 2.0,
                        "biomass": float(cell.get("biomass", 1.0)) / 2.0,
                        "generation": gen,
                        "parent": key,
                        "contents": {"chromosome": _chrom(_chrom_dna(chroms[i][1]))},
                    }
                self._divisions += 1

        # ── aggregates ──
        cells = _cells(colony)
        tot_vol = sum(float(v.get("volume", 1.0)) for _, v in cells)
        tot_dna = sum(_cell_dna(v) for _, v in cells)
        tot_nuc = sum(float(v.get("nucleotides", 0.0)) for _, v in cells)
        tot_bm = sum(float(v.get("biomass", 1.0)) for _, v in cells)
        tot_en = sum(float(v.get("energy", 0.0)) for _, v in cells)

        return {
            "colony": colony,
            "substrate": -total_uptake,
            "cell_count": self._set("cell_count", float(len(cells))),
            "tot_volume": self._set("tot_volume", tot_vol),
            "tot_dna": self._set("tot_dna", tot_dna),
            "tot_nucleotides": self._set("tot_nucleotides", tot_nuc),
            "tot_biomass": self._set("tot_biomass", tot_bm),
            "tot_energy": self._set("tot_energy", tot_en),
            "divisions": self._set("divisions", float(self._divisions)),
        }
