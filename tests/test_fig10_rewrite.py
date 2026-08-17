"""Fig 10.1 as a time-driven, engine-stepped rewrite: running the composite makes
the PLACE GRAPH change over successive steps — chromosome segregation (1→2) then
cell division (1→2 daughters) — captured as per-step frames a viewer can play.

Complements test_structural.py (a single division) with the multi-event cell
cycle used by the loom run/animate feature.
"""
from __future__ import annotations

from process_bigraph import Composite, gather_emitter_results

from viva_meta_modelers_guide.core import build_core
from viva_meta_modelers_guide.fig10_rewrite import build_fig10_division


def _nodes(node, control):
    """All descendant node keys whose _control == control (walks a tree[node] value)."""
    out = []
    if not isinstance(node, dict):
        return out
    for k, v in node.items():
        if k.startswith("_") or not isinstance(v, dict):
            continue
        if v.get("_control") == control:
            out.append(k)
        out += _nodes(v, control)
    return out


def _find_node(node, key):
    """The value stored at `key` anywhere in the tree (first match, depth-first)."""
    if not isinstance(node, dict):
        return None
    for k, v in node.items():
        if k == key:
            return v
        if isinstance(v, dict):
            found = _find_node(v, key)
            if found is not None:
                return found
    return None


def _dna_of(chrom):
    """The DNA amount on a chromosome node — directly on it or under `contents`."""
    if not isinstance(chrom, dict):
        return None
    if "dna" in chrom:
        return chrom["dna"]
    contents = chrom.get("contents")
    return contents.get("dna") if isinstance(contents, dict) else None


def _run_frames(cycle=3.0, interval=1.0, total=8.0):
    core = build_core()
    sim = Composite(build_fig10_division(cycle=cycle, interval=interval), core=core)
    sim.run(total)
    return [r["colony"] for r in gather_emitter_results(sim)[("emitter",)]]


def test_starts_as_one_cell_one_chromosome():
    frames = _run_frames()
    assert _nodes(frames[0], "cell") == ["cell"]
    assert _nodes(frames[0], "chromosome") == ["chromosome"]


def test_chromosome_segregates_before_division():
    frames = _run_frames()
    # somewhere in the run the single chromosome becomes two, while still one cell
    seg = [f for f in frames
           if len(_nodes(f, "chromosome")) == 2 and len(_nodes(f, "cell")) == 1]
    assert seg, "chromosome never segregated (1->2) while still a single cell"


def test_cell_divides_into_two_daughters():
    frames = _run_frames()
    last = frames[-1]
    cells = _nodes(last, "cell")
    assert len(cells) == 2, f"expected 2 cells after division, got {cells}"
    # daughters keep the biological _control label (render correctly), not the trigger mark
    assert all(c != "cell" for c in cells)          # renamed daughters
    assert "replicate" not in str(last)             # the trigger mark is consumed


def test_topology_grows_monotonically():
    frames = _run_frames()
    cell_counts = [len(_nodes(f, "cell")) for f in frames]
    chr_counts = [len(_nodes(f, "chromosome")) for f in frames]
    assert cell_counts[0] == 1 and cell_counts[-1] == 2
    # Replication doubles the chromosome (1→2); division PARTITIONS them one per
    # daughter, so the two daughters hold two chromosomes total — not four.
    assert chr_counts[0] == 1 and chr_counts[-1] == 2
    assert max(chr_counts) == 2                            # never more than the two sisters
    assert cell_counts == sorted(cell_counts)             # never shrinks


def test_each_daughter_keeps_one_chromosome_with_dna():
    """The payoff: after division, each of the two daughters is its own cell with
    exactly ONE chromosome carrying its DNA (true partition, DNA preserved)."""
    frames = _run_frames()
    last = frames[-1]
    cells = _nodes(last, "cell")
    assert len(cells) == 2
    for ck in cells:
        cell = _find_node(last, ck)
        chroms = _nodes(cell, "chromosome")
        assert len(chroms) == 1, f"{ck} has {len(chroms)} chromosomes, expected 1"
        chrom = _find_node(cell, chroms[0])
        assert _dna_of(chrom) == 1.0, f"{ck}'s chromosome lost its DNA"
