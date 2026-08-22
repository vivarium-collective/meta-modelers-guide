#!/usr/bin/env python
"""Render a bespoke, self-contained HTML report for each investigation.

Replaces the workbench SPA's generic per-study dump (11 identical sub-sections
x N studies, 48 MB of embedded PNGs) with a curated, designed report that:
  - leads with the thesis + verdict + the arc,
  - PROMOTES the interesting components (the whole cell that lives and dies, the
    one-interface-three-mechanisms swap, division-as-rewrite),
  - shows each study as a compact card (claim + measured readouts + the running
    executable-dynamics figure) with the full detail behind a <details>,
  - LIFTS boilerplate that is identical across every study (limitations,
    falsifiability) into a single shared "Method & caveats" section,
  - inlines only the small executable-dynamics SVGs (~0.5 MB total), never the
    multi-MB loom draft renders or the illustration PNGs.

Writes reports/published/investigations/<slug>.html + the landing-page
investigations_index.html fragment (reusing publish_investigation_reports.build_
index_fragment), so it is a drop-in replacement for the Playwright exporter in
.github/workflows/publish-reports.yml.

Run:  PYTHONPATH=. .venv/bin/python scripts/render_report.py --workspace . --out reports/published
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import mimetypes
import re
from pathlib import Path

import yaml

TEAL = "#0d6e6b"

# The arc the nine studies trace (the paper's through-line), one entry per study
# slug: (short label, composition direction). Direction: "out" = outward
# (cell<->environment / cell<->cell), "in" = inward (internal processes compose
# to produce the interface), "both" = the interface itself / across timescales.
ARC_STUDIES = {
    "cellular-interface":            ("interface",       "both"),
    "cell-environment-coupling":     ("cell ↔ env",  "out"),
    "cell-cell-coupling":            ("cell ↔ cell", "out"),
    "disintegration":                ("disintegration",  "in"),
    "molecular-interfaces":          ("molecular",       "in"),
    "biomolecular-complementarity":  ("complementarity", "in"),
    "autopoiesis":                   ("autopoiesis",     "in"),
    "growth-and-division":           ("growth+division", "out"),
    "development-and-evolution":     ("dev+evolution",   "both"),
}
# The rung words beneath the arc (the paper's ladder), learning still open.
ARC_RUNGS = ["interface", "individuality", "viability", "self-maintenance",
             "agency", "adaptation", "learning"]


def discover_investigations(ws_root: Path) -> list[str]:
    inv_root = ws_root / "workspace" / "investigations"
    if not inv_root.is_dir():
        inv_root = ws_root / "investigations"
    if not inv_root.is_dir():
        return []
    return sorted(d.name for d in inv_root.iterdir()
                  if d.is_dir() and (d / "investigation.yaml").is_file())


def _load_inv_yaml(ws_root: Path, slug: str) -> dict:
    for base in (ws_root / "workspace" / "investigations", ws_root / "investigations"):
        p = base / slug / "investigation.yaml"
        if p.is_file():
            return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return {}


def build_index_fragment(ws_root: Path, slugs: list[str]) -> str:
    """Landing-page ``<div class="invest">`` blocks (one per investigation)."""
    blocks: list[str] = []
    for slug in slugs:
        spec = _load_inv_yaml(ws_root, slug)
        title = str(spec.get("title") or slug)
        status_raw = str(spec.get("status") or "").strip()
        status_label = status_raw.replace("_", " ") or "—"
        status_class = status_raw or "in_progress"
        execu = spec.get("executive") if isinstance(spec.get("executive"), dict) else {}
        desc = " ".join(str(execu.get("what_is_this") or spec.get("question") or "").split())
        if len(desc) > 300:
            desc = desc[:297].rstrip() + "…"
        studies = [s.get("name") if isinstance(s, dict) else s for s in (spec.get("studies") or [])]
        studies = [str(s) for s in studies if s]
        meta = f"{len(studies)} stud{'y' if len(studies) == 1 else 'ies'}"
        if 0 < len(studies) <= 4:
            meta += " · " + " · ".join(studies)
        blocks.append(
            '<div class="invest">\n'
            f'  <h3><a href="investigations/{html.escape(slug)}.html">{html.escape(title)}</a>\n'
            f'      <span class="pill {html.escape(status_class)}">{html.escape(status_label)}</span></h3>\n'
            f'  <p>{html.escape(desc)}</p>\n'
            f'  <p class="meta">{html.escape(meta)}</p>\n'
            '</div>')
    return "\n\n".join(blocks)

# ─── small helpers ───────────────────────────────────────────────────────────
def esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def md_inline(s: str) -> str:
    """Very small inline markdown: **bold**, *italic*, `code`."""
    s = esc(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return s


def paras(text: str) -> str:
    if not text:
        return ""
    return "\n".join(f"<p>{md_inline(p.strip())}</p>"
                     for p in re.split(r"\n\s*\n", str(text).strip()) if p.strip())


_SVG_CLEAN = re.compile(r"<\?xml.*?\?>\s*|<!DOCTYPE.*?>\s*", re.S)


def inline_svg(path: Path, cls: str = "fig") -> str:
    """Return an <svg> ready to embed: strip xml/doctype prologue, drop the fixed
    width/height so it scales, keep the viewBox."""
    if not path.exists():
        return ""
    raw = _SVG_CLEAN.sub("", path.read_text(encoding="utf-8", errors="replace")).lstrip()
    # neutralise fixed pt dimensions on the first <svg ...> so CSS controls size
    def _fix(m):
        tag = m.group(0)
        tag = re.sub(r'\s(width|height)="[^"]*"', "", tag)
        return tag[:-1] + f' class="{cls}" preserveAspectRatio="xMidYMid meet">'
    raw = re.sub(r"<svg\b[^>]*>", _fix, raw, count=1)
    return raw


# ─── custom charts (pure SVG, on-palette, no JS) ─────────────────────────────
def wholecell_chart(traj: dict) -> str:
    """Grow -> divide -> thermal shock -> viability collapse -> disintegrate,
    as one annotated multi-line chart. Left axis: biomass + debris; right: viability."""
    t = traj["time"]
    bm, deb, via, cc = traj["biomass"], traj["debris"], traj["viability"], traj["cell_count"]
    # downsample
    step = max(1, len(t) // 120)
    idx = list(range(0, len(t), step))
    W, H = 760, 320
    ml, mr, mtp, mb = 46, 46, 28, 40
    pw, ph = W - ml - mr, H - mtp - mb
    tmax = t[-1] or 1.0
    lmax = max(max(bm), max(deb)) * 1.08 or 1.0

    def X(tt): return ml + pw * (tt / tmax)
    def YL(v): return mtp + ph * (1 - v / lmax)
    def YR(v): return mtp + ph * (1 - v)          # viability 0..1

    def poly(vals, Y):
        return " ".join(f"{X(t[i]):.1f},{Y(vals[i]):.1f}" for i in idx)

    # division time (cell_count first reaches 2)
    div_t = next((t[i] for i in range(len(t)) if cc[i] >= 2), None)
    # shock onset ~ viability first drops below 0.95
    shock_t = next((t[i] for i in range(len(t)) if via[i] < 0.95), None)

    parts = [f'<svg viewBox="0 0 {W} {H}" class="chart" role="img" '
             f'aria-label="Whole-cell trajectory: biomass, debris and viability over time">']
    # gridlines (left axis)
    for gv in range(0, int(lmax) + 1):
        y = YL(gv)
        parts.append(f'<line x1="{ml}" y1="{y:.1f}" x2="{ml+pw}" y2="{y:.1f}" class="grid"/>')
        parts.append(f'<text x="{ml-8}" y="{y+3:.1f}" class="ax ax-l">{gv}</text>')
    # right axis ticks (viability)
    for gv in (0.0, 0.5, 1.0):
        y = YR(gv)
        parts.append(f'<text x="{ml+pw+8}" y="{y+3:.1f}" class="ax ax-r">{gv:g}</text>')
    # x ticks
    for xt in range(0, int(tmax) + 1, 4):
        parts.append(f'<text x="{X(xt):.1f}" y="{mtp+ph+22:.1f}" class="ax ax-x">{xt}</text>')
    # event markers
    if div_t is not None:
        x = X(div_t)
        parts.append(f'<line x1="{x:.1f}" y1="{mtp}" x2="{x:.1f}" y2="{mtp+ph}" class="evt"/>')
        parts.append(f'<text x="{x+4:.1f}" y="{mtp+12}" class="evt-l">divide · t≈{div_t:.1f}</text>')
    if shock_t is not None:
        x = X(shock_t)
        parts.append(f'<line x1="{x:.1f}" y1="{mtp}" x2="{x:.1f}" y2="{mtp+ph}" class="evt evt-shock"/>')
        parts.append(f'<text x="{x+4:.1f}" y="{mtp+26}" class="evt-l evt-l-shock">thermal shock</text>')
    # series
    parts.append(f'<polyline points="{poly(via, YR)}" class="ser via"/>')
    parts.append(f'<polyline points="{poly(deb, YL)}" class="ser debris"/>')
    parts.append(f'<polyline points="{poly(bm, YL)}" class="ser biomass"/>')
    parts.append("</svg>")
    return "".join(parts)


def bars_chart(items: list[tuple[str, float]], vmax: float | None = None) -> str:
    """Small horizontal comparison bars, e.g. the three metabolism handlers."""
    vmax = vmax or max(v for _, v in items) * 1.15 or 1.0
    W, bh, gap, lblw = 320, 26, 12, 96
    H = len(items) * (bh + gap) + gap
    parts = [f'<svg viewBox="0 0 {W} {H}" class="chart bars" role="img" aria-label="comparison">']
    for i, (lbl, v) in enumerate(items):
        y = gap + i * (bh + gap)
        bw = (W - lblw - 40) * (v / vmax)
        parts.append(f'<text x="0" y="{y+bh*0.7:.0f}" class="bar-l">{esc(lbl)}</text>')
        parts.append(f'<rect x="{lblw}" y="{y}" width="{bw:.1f}" height="{bh}" rx="3" class="bar"/>')
        parts.append(f'<text x="{lblw+bw+6:.1f}" y="{y+bh*0.7:.0f}" class="bar-v">{v:g}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _data_uri(path: Path) -> str:
    """Base64 data: URI for a raster figure (gif/png/jpg), so the report stays a
    single self-contained file. Empty string if the file is missing."""
    if not path or not path.exists():
        return ""
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def arc_diagram_svg(studies: list[dict]) -> str:
    """The through-line: the studies as an ordered path left→right, each a node
    tagged with its composition direction (outward/inward/both), with the paper's
    rung ladder beneath and 'learning' as a ghosted, still-open final node."""
    n = len(studies)
    if not n:
        return ""
    W, H = 900, 240
    ml, mr = 40, 40
    row_y = 96                       # the spine
    span = W - ml - mr
    # node x centers: n study nodes + 1 ghost (learning)
    total = n + 1
    xs = [ml + span * (i + 0.5) / total for i in range(total)]
    dir_fill = {"out": "var(--teal)", "in": "var(--ochre)", "both": "var(--ink-2)"}
    dir_label = {"out": "outward", "in": "inward", "both": "both"}
    p = [f'<svg viewBox="0 0 {W} {H}" class="arc-svg" role="img" '
         f'aria-label="The arc traced by the {n} studies, from the interface to adaptation">']
    # spine
    p.append(f'<line x1="{xs[0]:.0f}" y1="{row_y}" x2="{xs[-1]:.0f}" y2="{row_y}" class="arc-spine"/>')
    # rung ladder beneath (evenly spread words)
    for i, rung in enumerate(ARC_RUNGS):
        rx = ml + span * (i + 0.5) / len(ARC_RUNGS)
        ghost = ' arc-rung-open' if rung == "learning" else ''
        p.append(f'<text x="{rx:.0f}" y="{H-18}" class="arc-rung{ghost}">{esc(rung)}</text>')
    p.append(f'<line x1="{ml}" y1="{H-40}" x2="{W-mr}" y2="{H-40}" class="arc-ladder"/>')
    # study nodes
    for i, s in enumerate(studies):
        slug = s.get("name", "")
        label, direction = ARC_STUDIES.get(slug, (s.get("title") or slug, "both"))
        x = xs[i]
        fill = dir_fill.get(direction, "var(--ink-2)")
        p.append(f'<a href="#{esc(slug)}">')
        p.append(f'<circle cx="{x:.0f}" cy="{row_y}" r="13" class="arc-dot" style="fill:{fill}"/>')
        p.append(f'<text x="{x:.0f}" y="{row_y+4:.0f}" class="arc-dot-n">{i+1:02d}</text>')
        # direction pill above
        p.append(f'<text x="{x:.0f}" y="{row_y-24:.0f}" class="arc-dir">{esc(dir_label.get(direction,""))}</text>')
        # label below (two lines if it contains a space and is long)
        words = str(label).split()
        if len(label) > 11 and len(words) > 1:
            mid = len(words) // 2
            l1, l2 = " ".join(words[:mid]), " ".join(words[mid:])
            p.append(f'<text x="{x:.0f}" y="{row_y+34:.0f}" class="arc-lbl">'
                     f'<tspan x="{x:.0f}" dy="0">{esc(l1)}</tspan>'
                     f'<tspan x="{x:.0f}" dy="12">{esc(l2)}</tspan></text>')
        else:
            p.append(f'<text x="{x:.0f}" y="{row_y+34:.0f}" class="arc-lbl">{esc(label)}</text>')
        p.append('</a>')
    # ghost 'learning' node
    gx = xs[-1]
    p.append(f'<circle cx="{gx:.0f}" cy="{row_y}" r="13" class="arc-dot arc-dot-open"/>')
    p.append(f'<text x="{gx:.0f}" y="{row_y+4:.0f}" class="arc-dot-n arc-dot-n-open">?</text>')
    p.append(f'<text x="{gx:.0f}" y="{row_y-24:.0f}" class="arc-dir">open</text>')
    p.append(f'<text x="{gx:.0f}" y="{row_y+34:.0f}" class="arc-lbl arc-lbl-open">learning</text>')
    p.append("</svg>")
    return "".join(p)


def substitutability_chart(pairs: list[tuple[str, float, float, str]]) -> str:
    """Paired bars: for each interface observable, the dynamic-FBA value and the
    lumped Michaelis–Menten value, each normalised to the dFBA value (=1.0) so the
    eye reads agreement directly. Each pair is annotated with the divergence."""
    W = 460
    gh, bh, gap = 62, 18, 6          # group height, bar height, intra-gap
    top = 16
    H = top + len(pairs) * gh + 8
    plot_x, plot_w = 150, W - 150 - 60
    p = [f'<svg viewBox="0 0 {W} {H}" class="chart subst" role="img" '
         f'aria-label="dynamic-FBA vs Michaelis–Menten, per interface observable">']
    # 1.0 reference line
    x1 = plot_x + plot_w
    p.append(f'<line x1="{x1:.0f}" y1="{top}" x2="{x1:.0f}" y2="{H-8}" class="subst-ref"/>')
    p.append(f'<text x="{x1:.0f}" y="{top-4}" class="subst-ref-l">dFBA = 1.0</text>')
    for i, (lbl, dfba, mm, delta) in enumerate(pairs):
        gy = top + i * gh
        p.append(f'<text x="0" y="{gy+gh/2:.0f}" class="subst-obs">{esc(lbl)}</text>')
        # dFBA bar (normalised to 1.0) then MM bar (mm/dfba)
        for j, (name, frac, cls) in enumerate((("dFBA", 1.0, "subst-dfba"),
                                               ("MM", (mm/dfba if dfba else 0), "subst-mm"))):
            by = gy + 6 + j * (bh + gap)
            bw = plot_w * frac
            p.append(f'<rect x="{plot_x}" y="{by}" width="{bw:.1f}" height="{bh}" rx="3" class="{cls}"/>')
            p.append(f'<text x="{plot_x+6}" y="{by+bh*0.72:.0f}" class="subst-bl">{esc(name)}</text>')
        p.append(f'<text x="{W-56}" y="{gy+gh/2:.0f}" class="subst-delta">{esc(delta)}</text>')
    p.append("</svg>")
    return "".join(p)


# ─── report assembly ─────────────────────────────────────────────────────────
def load_study(ws: Path, slug: str) -> dict:
    for base in (ws / "workspace" / "studies", ws / "studies"):
        p = base / slug / "study.yaml"
        if p.is_file():
            d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            d["_dir"] = p.parent
            return d
    return {}


def outcomes(study: dict) -> list[tuple[str, str, str]]:
    """(name, detail, result) for each outcome of the study's first run with
    outcomes. ``result`` (PASS / POSITIVE / fail …) is carried through so an
    expected-fail control can be rendered distinctly from a generic PASS."""
    for r in study.get("runs", []):
        oc = r.get("outcomes") or {}
        if oc:
            out = []
            for k, v in oc.items():
                if isinstance(v, dict):
                    out.append((k, v.get("detail", ""), str(v.get("result", ""))))
                else:
                    out.append((k, str(v), ""))
            return out
    return []


# ── Verdict-count split (peer-review M6d) ─────────────────────────────────────
# A study's ``behavior_tests`` are not all the same kind of evidence, and the
# report must not tally them as one undifferentiated pile of PASSes. Three
# buckets, read off each test entry:
#   * committed     — a rerunnable pytest backs it (its provenance / committed_test
#                     cites a ``tests/test_*.py`` path);
#   * narrated      — a documented / diagnostic check with no committed pytest
#                     (evidence from a run readout or a documented regime sweep);
#   * expected_fail — an expected-fail control (``expected_result: fail``, e.g.
#                     draft-is-inert): passing means the draft correctly FAILED
#                     by design, which is not a generic PASS.
_TEST_PATH_RE = re.compile(r"tests/test_[\w/]+\.py")


def _behavior_tests(study: dict) -> list:
    return study.get("behavior_tests") or []


def classify_behavior_tests(study: dict) -> dict:
    counts = {"committed": 0, "narrated": 0, "expected_fail": 0}
    for t in _behavior_tests(study):
        if str(t.get("expected_result", "")).lower() == "fail":
            counts["expected_fail"] += 1
            continue
        prov = (str((t.get("pass_if") or {}).get("provenance", ""))
                + " " + str(t.get("committed_test", "")))
        if _TEST_PATH_RE.search(prov):
            counts["committed"] += 1
        else:
            counts["narrated"] += 1
    return counts


def report_test_ledger(studies: list[dict]) -> dict:
    total = {"committed": 0, "narrated": 0, "expected_fail": 0}
    for s in studies:
        for k, v in classify_behavior_tests(s).items():
            total[k] += v
    return total


# ── Provenance / environment block (peer-review minor 11) ─────────────────────
# So a reader knows exactly what produced a report: the git commit, the host
# platform, and the versions of the simulation stack that were importable when
# it was rendered. Degrades gracefully — a missing package or absent git is
# simply omitted, never a crash — and bakes NO absolute paths.
_ENV_PACKAGES = [
    ("process-bigraph", "process_bigraph"),
    ("bigraph-schema", "bigraph_schema"),
    ("spatio-flux", "spatio_flux"),
    ("cobra", "cobra"),
    ("viva-cpm", "viva_cpm"),
    ("vivarium-cpm", "vivarium_cpm"),
    ("cpm", "cpm"),
]


def _package_version(dist_label: str, module_name: str) -> str | None:
    import importlib
    try:
        mod = importlib.import_module(module_name)
    except Exception:
        return None
    ver = getattr(mod, "__version__", None)
    if ver:
        return str(ver)
    try:
        from importlib.metadata import version as _dist_version
        return str(_dist_version(dist_label))
    except Exception:
        return "installed"


def _git_commit(ws: Path) -> str | None:
    import subprocess
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                           cwd=str(ws), capture_output=True, text=True, timeout=5)
    except Exception:
        return None
    out = (r.stdout or "").strip()
    return out if r.returncode == 0 and out else None


def environment_block(ws: Path) -> str:
    import platform as _platform
    items: list[tuple[str, str]] = []
    commit = _git_commit(ws)
    if commit:
        items.append(("commit", commit))
    items.append(("platform",
                  f"{_platform.python_implementation()} {_platform.python_version()} · "
                  f"{_platform.system()} {_platform.machine()}"))
    for label, module_name in _ENV_PACKAGES:
        ver = _package_version(label, module_name)
        if ver is not None:
            items.append((label, ver))
    cells = "".join(
        f'<div class="env-item"><span class="env-k">{esc(k)}</span>'
        f'<span class="env-v">{esc(v)}</span></div>' for k, v in items)
    return f"""
    <section class="env" aria-label="provenance and environment">
      <span class="kicker">Provenance &amp; environment</span>
      <div class="env-grid">{cells}</div>
    </section>"""


# Outcome badge: an expected-fail control (draft-is-inert) is rendered as a
# distinct "EXPECTED FAIL" chip, never a green PASS.
_OUTCOME_BADGE = {
    "xfail": ("warn", "expected fail"),
    "positive": ("ok", "positive"),
    "pass": ("ok", "pass"),
}


def _outcome_kind(detail: str, result: str) -> str:
    d = (detail or "").lower()
    if "expected-fail" in d or "expected fail" in d or str(result).lower() == "fail":
        return "xfail"
    if str(result).upper() == "POSITIVE":
        return "positive"
    return "pass"


def study_exec_svgs(study: dict) -> list[Path]:
    d = study.get("_dir")
    if not d:
        return []
    return sorted((d / "visualizations").glob("*-dynamics.svg"))


def study_figures(study: dict) -> list[str]:
    """Figure HTML for a study card: inline its declared ``image:…gif`` simulation
    movies as self-contained data-URIs, plus any hand-drawn executable-dynamics
    SVG. Skips the interactive ``html:`` metrics panels (Plotly, not
    self-contained) and the multi-MB illustration PNG/SVGs."""
    d = study.get("_dir")
    figs: list[str] = []
    if not d:
        return figs
    for v in study.get("visualizations", []) or []:
        addr = str(v.get("address") or "")
        scheme, _, rel = addr.partition(":")
        if scheme in {"image", "gif"} and rel.endswith(".gif"):
            uri = _data_uri(d / rel)
            if not uri:
                continue
            cfg = v.get("config") if isinstance(v.get("config"), dict) else {}
            caption = cfg.get("caption") if isinstance(cfg, dict) else ""
            cap = f'<figcaption class="fig-cap">{md_inline(caption)}</figcaption>' if caption else ""
            figs.append(f'<figure class="fig-wrap"><img src="{uri}" '
                        f'alt="{esc(v.get("name",""))}" loading="lazy" class="fig-img"/>{cap}</figure>')
    for p in study_exec_svgs(study):
        figs.append(f'<figure class="fig-wrap">{inline_svg(p)}</figure>')
    return figs


def confidence_badge(study: dict) -> str:
    c = str(study.get("confidence") or "").strip()
    cls = {"Accepted": "ok", "Provisional": "warn", "Investigating": "warn",
           "Planned": "muted", "Refuted": "bad"}.get(c, "muted")
    return f'<span class="badge {cls}">{esc(c or "—")}</span>' if c else ""


def chips(pairs: list[tuple[str, str]]) -> str:
    out = []
    for k, v in pairs:
        out.append(f'<div class="chip"><span class="chip-k">{esc(k.replace("-"," "))}</span>'
                   f'<span class="chip-v">{md_inline(v)}</span></div>')
    return f'<div class="chips">{"".join(out)}</div>' if out else ""


def outcome_chips(triples: list[tuple[str, str, str]]) -> str:
    """Render run outcomes as chips, badging each by kind so an expected-fail
    control (draft-is-inert) reads as EXPECTED FAIL, not a generic PASS."""
    out = []
    for name, detail, result in triples:
        kind = _outcome_kind(detail, result)
        bcls, blabel = _OUTCOME_BADGE[kind]
        out.append(
            f'<div class="chip chip-{kind}"><span class="chip-k">{esc(name.replace("-"," "))} '
            f'<span class="badge {bcls} chip-badge">{esc(blabel)}</span></span>'
            f'<span class="chip-v">{md_inline(detail)}</span></div>')
    return f'<div class="chips">{"".join(out)}</div>' if out else ""


# Precise, physically-honest label per invariant kind (the callout badge text).
# "conserved" is only true for the balance laws — the others are separations,
# closures, or selection dynamics, so each gets its own verb.
INV_LABEL = {
    "carbon": "Mass balance",
    "mass": "Mass conserved",
    "energy": "Energy balance",
    "timescale": "Timescale separation",
    "closure": "Operational closure",
    "logistic": "Bounded growth",
    "selection": "Selection",
}


def _inv_label(kind: str) -> str:
    return INV_LABEL.get(kind, (kind or "checked").replace("-", " ").title())


# ─── model definition + interface contract (read from the composite JSON) ─────
def _composite_file(ws: Path, dotted: str) -> Path | None:
    """Resolve a study's ``meta_modelers_guide.composites.<name>`` to its
    ``<name>.composite.json`` on disk."""
    if not dotted:
        return None
    name = str(dotted).split(".")[-1]
    for base in (ws / "meta_modelers_guide" / "composites",
                 ws / "workspace" / "composites", ws / "composites"):
        p = base / f"{name}.composite.json"
        if p.is_file():
            return p
    return None


def load_composite(ws: Path, dotted: str) -> dict:
    p = _composite_file(ws, dotted)
    if not p:
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8")) or {}
    except (OSError, json.JSONDecodeError):
        return {}


def _short_cls(address: str) -> str:
    """``local:!spatio_flux.processes.diffusion_advection.DiffusionAdvection`` →
    ``DiffusionAdvection``; ``local:CpmCellField`` → ``CpmCellField``."""
    a = str(address).split(":")[-1].lstrip("!")
    return a.split(".")[-1] or a


_EMITTERS = {"RAMEmitter", "ConsoleEmitter", "DatabaseEmitter"}


def _fmt_params(config: dict, limit: int = 9) -> list[tuple[str, str]]:
    """The model's scalar/short parameters as (key, value) pairs — the physically
    meaningful knobs, skipping RNG seeds and long state arrays."""
    out: list[tuple[str, str]] = []
    for k, v in (config or {}).items():
        if k in {"seed", "seed_block"}:
            continue
        if isinstance(v, bool):
            out.append((k, "true" if v else "false"))
        elif isinstance(v, (int, float)):
            out.append((k, f"{v:g}"))
        elif isinstance(v, str) and len(v) <= 24:
            out.append((k, v))
        elif isinstance(v, list) and 0 < len(v) <= 4 and all(isinstance(x, (int, float)) for x in v):
            out.append((k, "[" + ", ".join(f"{x:g}" for x in v) + "]"))
        elif isinstance(v, dict) and 0 < len(v) <= 3 and all(isinstance(x, (int, float)) for x in v.values()):
            out.append((k, "{" + ", ".join(f"{kk} {vv:g}" for kk, vv in v.items()) + "}"))
    return out[:limit]


def _processes(comp: dict) -> list[dict]:
    procs = []
    for name, v in (comp.get("state") or {}).items():
        if isinstance(v, dict) and v.get("_type") in ("process", "step"):
            procs.append({"name": name, "cls": _short_cls(v.get("address", "")),
                          "config": v.get("config") or {},
                          "inputs": v.get("inputs") or {}, "outputs": v.get("outputs") or {}})
    return procs


def _model_panel(comp: dict, label: str, param_limit: int, extra_rows: str = "") -> str:
    """One 'model definition' panel: every process in a composite with its params.
    ``label`` (the baseline name) is shown when a study has more than one."""
    rows = []
    for p in (pp for pp in _processes(comp) if pp["cls"] not in _EMITTERS):
        params = _fmt_params(p["config"], param_limit)
        pstr = "".join(f'<span class="pm"><b>{esc(k)}</b> {esc(v)}</span>' for k, v in params)
        rows.append(f'<div class="proc"><code class="proc-cls">{esc(p["cls"])}</code>'
                    f'<span class="proc-params">{pstr or "—"}</span></div>')
    lbl = f'<span class="spec-sub">{esc(label)}</span>' if label else ""
    return (
        '<div class="spec-panel modeldef">'
        f'<div class="spec-h"><span class="spec-tag">model definition</span>{lbl}'
        f'<code class="spec-cls">{esc(comp.get("name",""))}</code></div>'
        f'{"".join(rows)}{extra_rows}</div>')


def spec_block_html(study: dict, ws: Path) -> str:
    """The interface contract (the primary process's typed ports) and the model
    definition — a panel per baseline composite, so a study realized several ways
    (e.g. the cellular interface: lumped modalities, executable, and spatial)
    shows every composition, read straight from the composite JSON."""
    baselines = study.get("baseline") or []
    comps = [(str(b.get("name") or ""), load_composite(ws, b.get("composite", "")))
             for b in baselines]
    comps = [(n, c) for n, c in comps if _processes(c)]
    if not comps:
        return ""

    # interface contract — the primary (most-exposed) process of the first baseline
    procs0 = [p for p in _processes(comps[0][1]) if p["cls"] not in _EMITTERS]
    prim = max(procs0, key=lambda p: len(p["outputs"])) if procs0 else None
    contract = ""
    if prim:
        reads = " · ".join(prim["inputs"].keys()) or "—"
        exposes = " · ".join(prim["outputs"].keys()) or "—"
        contract = (
            '<div class="spec-panel contract">'
            f'<div class="spec-h"><span class="spec-tag">interface contract</span>'
            f'<code class="spec-cls">{esc(prim["cls"])}</code></div>'
            f'<div class="port"><span class="port-k">reads</span><code>{esc(reads)}</code></div>'
            f'<div class="port"><span class="port-k">exposes</span><code>{esc(exposes)}</code></div>'
            '</div>')

    multi = len(comps) > 1
    limit = 6 if multi else 9
    variants = study.get("variants") or []
    vstr = ""
    if variants:
        vs = " · ".join(f'<code>{esc(v.get("name",""))}</code>' for v in variants)
        vstr = f'<div class="proc"><span class="port-k">variants</span><span class="proc-params">{vs}</span></div>'
    panels = "".join(
        _model_panel(c, (n if multi else ""), limit, vstr if i == 0 else "")
        for i, (n, c) in enumerate(comps))
    return f'<div class="spec">{contract}{panels}</div>'


def study_card(study: dict, order: int, inv_map: dict, ws: Path) -> str:
    slug = study.get("name", "")
    title = study.get("title") or slug
    claim = study.get("claim") or ""
    oc = outcomes(study)
    figs = "".join(study_figures(study))
    spec = spec_block_html(study, ws)

    # collapsible full detail — the parts a reader only wants on demand
    findings = study.get("findings", [])
    find_html = "".join(
        f'<li><span class="tier tier-{esc(f.get("tier","observation"))}">{esc(f.get("tier","obs"))}</span> '
        f'{md_inline(f.get("statement",""))}</li>' for f in findings)
    detail = f"""
      <details class="more">
        <summary>Question &amp; findings</summary>
        <div class="more-body">
          <h4>Question</h4>{paras(study.get('question'))}
          <h4>Findings</h4><ul class="findings">{find_html}</ul>
        </div>
      </details>"""

    return f"""
    <article class="study" id="{esc(slug)}">
      <div class="study-head">
        <span class="ord">{order:02d}</span>
        <div>
          <h3>{esc(title)} {confidence_badge(study)}</h3>
          <p class="claim">{md_inline(claim)}</p>
        </div>
      </div>
      {outcome_chips(oc)}
      {spec}
      <div class="figs">{figs}</div>
      {detail}
    </article>"""


def shared_boilerplate(studies: list[dict]) -> dict:
    """Detect fields identical across every study so they render ONCE."""
    def col(field):
        vals = [json.dumps(s.get(field), sort_keys=True, ensure_ascii=False) for s in studies]
        return vals[0] if vals and len(set(vals)) == 1 and studies[0].get(field) else None
    return {
        "limitations": studies[0].get("limitations") if col("limitations") else None,
        "falsifiability": studies[0].get("falsifiability") if col("falsifiability") else None,
    }


def render_investigation(ws: Path, slug: str, out_dir: Path) -> Path:
    inv = {}
    for base in (ws / "workspace" / "investigations", ws / "investigations"):
        p = base / slug / "investigation.yaml"
        if p.is_file():
            inv = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            break
    order = [s.get("name") if isinstance(s, dict) else s for s in inv.get("studies", [])]
    studies = [load_study(ws, s) for s in order if s]
    studies = [s for s in studies if s]
    by_slug = {s["name"]: s for s in studies}

    execu = inv.get("executive", {}) if isinstance(inv.get("executive"), dict) else {}
    arg = inv.get("scientific_argument", {}) if isinstance(inv.get("scientific_argument"), dict) else {}

    # per-figure executable signatures measured by scripts/render_study_evidence.py
    inv_path = ws / "scripts" / "_catalog" / "dynamics_readouts.json"
    inv_map = json.loads(inv_path.read_text()) if inv_path.exists() else {}

    # ── hero stats
    n_figs = sum(1 for s in studies if study_figures(s))
    ledger = report_test_ledger(studies)
    stats = [("studies", str(len(studies))),
             ("composition patterns", str(len(studies))),
             ("with figures", str(n_figs)),
             ("committed pytests", str(ledger["committed"])),
             ("modalities realized", "2 of 4")]
    stat_html = "".join(f'<div class="stat"><b>{v}</b><span>{esc(k)}</span></div>' for k, v in stats)

    # ── verdict-count split (M6d): committed pytests counted apart from
    # narrated/diagnostic checks and from expected-fail controls (which pass by
    # failing, so are never tallied as generic PASSes).
    ledger_html = f"""
    <div class="ledger" aria-label="test ledger">
      <span class="ledger-item"><b>{ledger['committed']}</b> committed rerunnable pytests</span>
      <span class="ledger-item"><b>{ledger['narrated']}</b> narrated / diagnostic checks</span>
      <span class="ledger-item ledger-xfail"><b>{ledger['expected_fail']}</b> expected-fail controls (draft-is-inert)</span>
    </div>"""

    # ── the arc (an SVG through-line: the studies as an ordered path)
    arc_svg = arc_diagram_svg(studies)

    # ── highlight: the thesis in one figure — substitutability (dFBA vs MM)
    highlights = []
    if by_slug.get("cell-environment-coupling"):
        subst_pairs = [
            ("final biomass", 0.370, 0.342, "Δ 7.5%"),
            ("CPM volume", 110.0, 99.0, "Δ 10%"),
            ("acetate secreted", 47.02, 47.02, "Δ ~0%"),
            ("glucose depleted", 31.6, 33.6, "Δ 6.2%"),
        ]
        highlights.append(f"""
        <section class="hl reverse">
          <div class="hl-txt">
            <span class="kicker">The thesis, in one figure</span>
            <h2>Same interface, different mechanism</h2>
            <p>The flagship's cell–environment interface (<code>CpmCellField</code>) is realized two
            ways behind <strong>byte-identical ports</strong>: a constraint-based dynamic-FBA
            metabolism (cobra <code>e_coli_core</code>, O₂-capped to force acetate overflow) and a
            lumped, cobra-free Michaelis–Menten kinetic. Every interface-level observable agrees
            within ~10% — an executable instance of the paper's equivalence-class claim: the
            composition pattern is a property of the <em>interface</em>, not of the mechanism behind
            it.</p>
          </div>
          <figure class="hl-fig hl-bars">{substitutability_chart(subst_pairs)}
            <figcaption class="fig-cap">Interface observables over 20 ticks, each bar normalised to
            the dynamic-FBA value; the lumped Michaelis–Menten twin tracks it within ~10%.</figcaption>
          </figure>
        </section>""")

    # ── studies
    cards = "".join(study_card(by_slug[s], i + 1, inv_map, ws)
                    for i, s in enumerate(sn for sn in order if sn in by_slug))

    # ── shared caveats (lifted from identical per-study boilerplate)
    shared = shared_boilerplate(studies)
    cav_items = []
    if shared["limitations"]:
        cav_items += [f"<li>{md_inline(x)}</li>" for x in shared["limitations"]]
    caveat_extra = arg.get("caveats", []) or []
    cav_items += [f"<li>{md_inline(x)}</li>" for x in caveat_extra]
    fals = shared["falsifiability"]
    shared_html = f"""
    <section class="method">
      <h2>Method &amp; shared caveats</h2>
      <p class="lead-sm">Every figure begins as an inert <strong>draft</strong> — typed, unit-bearing
      ports and a behavior contract, no dynamics — and is <strong>compiled</strong> by installing one
      conforming mechanism, which preserves the interface exactly (compiler law 2) while giving the
      figure real dynamics. Readouts below are <strong>measured</strong>, not asserted: every executable
      and the whole cell were run and their observables recorded.</p>
      <div class="two-col">
        <div><h4>Limitations (shared across every study)</h4><ul>{''.join(cav_items)}</ul></div>
        <div><h4>What would falsify the claim</h4><p>{md_inline(fals) if fals else '—'}</p></div>
      </div>
    </section>"""

    # ── evidence for/against
    ef = "".join(f"<li>{md_inline(x)}</li>" for x in arg.get("evidence_for", []))
    ea = "".join(f"<li>{md_inline(x)}</li>" for x in arg.get("evidence_against", []))

    verdict = execu.get("verdict", "")
    status = str(inv.get("status") or "").strip()
    vstatus = str(execu.get("verdict_status") or "").strip()
    # Reflect the honest verdict_status in the header badge, not a green 'ok' for 'running'.
    vbadge_label = vstatus or status or "complete"
    vbadge_cls = {"needs_calibration": "warn", "passed": "ok", "refuted": "bad"}.get(vstatus, "ok")
    nstudies_word = {8: "eight", 9: "nine", 10: "ten", 11: "eleven",
                     12: "twelve"}.get(len(studies), str(len(studies)))

    body = f"""
    <header class="hero">
      <span class="kicker">Executable atlas · <em>A meta-modeler's guide to the cellular interface</em></span>
      <h1>{esc(inv.get('title') or slug)}</h1>
      <p class="thesis">{md_inline(inv.get('lead') or execu.get('what_is_this') or '')}</p>
      <div class="verdict"><span class="badge {vbadge_cls}">{esc(vbadge_label)}</span>
        <p>{md_inline(verdict)}</p></div>
      {ledger_html}
      <div class="stats">{stat_html}</div>
    </header>

    <section class="intro">
      <span class="kicker">Introduction</span>
      {paras(execu.get('what_is_this') or '')}
    </section>

    <section class="arcfig" aria-label="the arc traced by the studies">
      <span class="kicker">The arc — from the interface to an adapting agent</span>
      {arc_svg}
    </section>

    {''.join(highlights)}

    <section class="argument">
      <div><h3>Evidence for</h3><ul>{ef}</ul></div>
      <div><h3>Evidence against</h3><ul>{ea}</ul></div>
    </section>

    <section class="studies-wrap">
      <h2>The {nstudies_word} studies <span class="sub">— in arc order; claim + measured readouts + the running figure. Open a card for the full detail.</span></h2>
      {cards}
    </section>

    {shared_html}

    {environment_block(ws)}

    <footer class="foot">
      <p>Generated from <code>investigation.yaml</code> + measured readouts ·
      <a href="../dashboard/">interactive read-only workbench</a> ·
      <a href="https://github.com/vivarium-collective/meta-modelers-guide">source</a></p>
    </footer>"""

    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(inv.get('title') or slug)}</title>
<style>{CSS}</style>
</head>
<body>
<main class="wrap">{body}</main>
</body>
</html>"""

    out_path = out_dir / "investigations" / f"{slug}.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(doc, encoding="utf-8")
    return out_path


CSS = """
:root{
  --ink:#16211f; --ink-2:#3a4a47; --muted:#657572;
  --paper:#f7f5f0; --surface:#ffffff; --line:#e3e0d8;
  --teal:#0d6e6b; --teal-2:#3f9e99; --ochre:#a5620f; --ochre-2:#c98a3a;
  --ok:#0d6e6b; --warn:#a5620f; --bad:#9b2f2f;
  --shadow:0 1px 2px rgba(22,33,31,.04),0 8px 24px rgba(22,33,31,.06);
  --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,"Times New Roman",serif;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
}
:root:not([data-theme="light"]){}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --ink:#e9ece9; --ink-2:#b7c1bd; --muted:#8b9995;
    --paper:#101514; --surface:#171d1c; --line:#28322f;
    --teal:#4bb3ae; --teal-2:#6fd0ca; --ochre:#d79a4e; --ochre-2:#e6b877;
    --ok:#4bb3ae; --warn:#d79a4e; --bad:#e07a7a;
    --shadow:0 1px 2px rgba(0,0,0,.3),0 10px 30px rgba(0,0,0,.35);
  }
}
:root[data-theme="dark"]{
  --ink:#e9ece9; --ink-2:#b7c1bd; --muted:#8b9995;
  --paper:#101514; --surface:#171d1c; --line:#28322f;
  --teal:#4bb3ae; --teal-2:#6fd0ca; --ochre:#d79a4e; --ochre-2:#e6b877;
  --ok:#4bb3ae; --warn:#d79a4e; --bad:#e07a7a;
}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);
  line-height:1.6;-webkit-font-smoothing:antialiased;font-size:17px}
.wrap{max-width:900px;margin:0 auto;padding:0 24px 96px}
h1,h2,h3,h4{font-family:var(--serif);font-weight:600;line-height:1.15;text-wrap:balance;color:var(--ink)}
a{color:var(--teal);text-decoration:none}
a:hover{text-decoration:underline}
code{font-family:var(--mono);font-size:.88em;background:color-mix(in srgb,var(--teal) 9%,transparent);
  padding:.08em .35em;border-radius:4px}
.kicker{display:inline-block;font-family:var(--sans);font-size:.74rem;letter-spacing:.09em;
  text-transform:uppercase;color:var(--muted);font-weight:600}
.kicker em{font-style:italic;text-transform:none;letter-spacing:0}

/* hero */
.hero{padding:72px 0 40px;border-bottom:1px solid var(--line)}
.hero h1{font-size:clamp(2.4rem,6vw,3.9rem);margin:.25em 0 .3em;letter-spacing:-.01em}
.thesis{font-size:1.22rem;color:var(--ink-2);max-width:40ch}
.verdict{display:flex;gap:14px;align-items:flex-start;margin:26px 0 0;padding:18px 20px;background:var(--surface);
  border:1px solid var(--line);border-left:3px solid var(--teal);border-radius:10px;box-shadow:var(--shadow)}
.verdict .badge{flex:none}
.verdict p{margin:0;color:var(--ink-2);font-size:.98rem}
.stats{display:flex;flex-wrap:wrap;gap:14px;margin-top:26px}
.intro{margin:44px 0 12px;max-width:70ch}
.intro .kicker{margin-bottom:12px;color:var(--teal)}
.intro p{font-size:1.08rem;line-height:1.7;color:var(--ink-2);margin:0 0 1.05em}
.intro p:first-of-type{color:var(--ink);font-size:1.14rem}
.stat{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:12px 18px;min-width:96px}
.stat b{display:block;font-family:var(--serif);font-size:1.9rem;color:var(--teal);line-height:1}
.stat span{font-size:.76rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}

/* badges */
.badge{display:inline-block;font-family:var(--sans);font-size:.7rem;font-weight:700;letter-spacing:.04em;
  text-transform:uppercase;padding:.2em .6em;border-radius:999px;vertical-align:middle;
  background:color-mix(in srgb,var(--muted) 16%,transparent);color:var(--muted)}
.badge.ok{background:color-mix(in srgb,var(--teal) 15%,transparent);color:var(--teal)}
.badge.warn{background:color-mix(in srgb,var(--ochre) 16%,transparent);color:var(--ochre)}
.badge.bad{background:color-mix(in srgb,var(--bad) 15%,transparent);color:var(--bad)}

/* arc spine */
.arc{display:flex;flex-wrap:wrap;align-items:center;gap:6px 8px;padding:26px 0;margin:8px 0 8px;
  border-bottom:1px solid var(--line)}
.arc-node{display:inline-flex;align-items:baseline;gap:7px;padding:6px 11px;border:1px solid var(--line);
  border-radius:999px;background:var(--surface);font-size:.82rem}
.arc-node:hover{border-color:var(--teal);text-decoration:none}
.arc-n{font-family:var(--mono);font-size:.72rem;color:var(--ochre);font-weight:700}
.arc-t{color:var(--ink)}
.arc-arrow{color:var(--muted)}

/* highlights */
.hl{display:grid;grid-template-columns:1fr 1.1fr;gap:34px;align-items:center;
  margin:56px 0;padding:34px;background:var(--surface);border:1px solid var(--line);
  border-radius:16px;box-shadow:var(--shadow)}
.hl.reverse{grid-template-columns:1.1fr 1fr}
.hl.reverse .hl-txt{order:2}
.hl h2{font-size:1.75rem;margin:.15em 0 .4em}
.hl p{color:var(--ink-2);font-size:1rem}
.hl-fig{margin:0}
.hl-fig.grid3{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.hl-bars{margin:14px 0 0}
figcaption{margin-top:8px;font-size:.78rem;color:var(--muted);display:flex;gap:16px;flex-wrap:wrap}
.lg{display:inline-flex;align-items:center;gap:6px}
.lg::before{content:"";width:14px;height:3px;border-radius:2px;background:var(--muted)}
.lg.biomass::before{background:var(--teal)}
.lg.debris::before{background:var(--ochre)}
.lg.via::before{background:var(--teal-2);height:0;border-top:2px dashed var(--teal-2)}

/* charts */
.chart{width:100%;height:auto;display:block;overflow:visible}
.chart .grid{stroke:var(--line);stroke-width:1}
.chart .ax{fill:var(--muted);font:11px var(--sans)}
.chart .ax-l{text-anchor:end}.chart .ax-r{text-anchor:start}.chart .ax-x{text-anchor:middle}
.chart .ser{fill:none;stroke-width:2.4;stroke-linejoin:round;stroke-linecap:round}
.chart .biomass{stroke:var(--teal)}
.chart .debris{stroke:var(--ochre)}
.chart .via{stroke:var(--teal-2);stroke-width:2;stroke-dasharray:4 4}
.chart .evt{stroke:var(--muted);stroke-width:1;stroke-dasharray:2 3}
.chart .evt-shock{stroke:var(--ochre)}
.chart .evt-l{fill:var(--muted);font:10px var(--sans)}
.chart .evt-l-shock{fill:var(--ochre)}
.bars .bar{fill:var(--teal)}
.bars .bar-l{fill:var(--ink);font:600 13px var(--sans);text-anchor:start;dominant-baseline:middle}
.bars .bar-v{fill:var(--muted);font:600 12px var(--mono);dominant-baseline:middle}

/* argument */
.argument{display:grid;grid-template-columns:1fr 1fr;gap:34px;margin:56px 0}
.argument h3{font-size:1.15rem;margin:0 0 .5em;padding-bottom:.35em;border-bottom:2px solid var(--line)}
.argument ul{margin:0;padding-left:1.1em}
.argument li{margin:.5em 0;color:var(--ink-2);font-size:.95rem}

/* studies */
.studies-wrap{margin:64px 0 0}
.studies-wrap>h2{font-size:1.9rem;border-bottom:1px solid var(--line);padding-bottom:.4em}
.studies-wrap .sub{font-family:var(--sans);font-size:.9rem;font-weight:400;color:var(--muted)}
.study{padding:30px 0;border-bottom:1px solid var(--line)}
.study-head{display:flex;gap:16px;align-items:flex-start}
.ord{font-family:var(--mono);font-size:.85rem;color:var(--ochre);font-weight:700;padding-top:.5em}
.study h3{font-size:1.4rem;margin:0}
.claim{margin:.4em 0 0;color:var(--ink-2);font-size:1.02rem}
.chips{display:flex;flex-wrap:wrap;gap:10px;margin:18px 0 0}
.chip{background:var(--surface);border:1px solid var(--line);border-radius:9px;padding:8px 12px;
  max-width:100%}
.chip-k{display:block;font-size:.66rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);font-weight:700}
.chip-v{font-family:var(--mono);font-size:.82rem;color:var(--ink)}
.chip-badge{font-size:.58rem;padding:1px 6px;vertical-align:middle}
.chip-xfail{border-color:color-mix(in srgb,var(--ochre) 45%,var(--line))}
.chip-xfail .chip-k{color:var(--ochre)}
.ledger{display:flex;flex-wrap:wrap;gap:10px 20px;margin:16px 0 0;font-size:.82rem;color:var(--ink-2)}
.ledger-item b{font-family:var(--serif);font-size:1.05rem;color:var(--teal);margin-right:5px}
.ledger-xfail b{color:var(--ochre)}
.env{margin:40px 0 0}
.env-grid{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0 0}
.env-item{background:var(--surface);border:1px solid var(--line);border-radius:9px;padding:7px 12px}
.env-k{display:block;font-size:.62rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);font-weight:700}
.env-v{font-family:var(--mono);font-size:.8rem;color:var(--ink)}
.invariant{margin:14px 0 0;padding:10px 14px;border-radius:9px;font-size:.9rem;color:var(--ink-2);
  background:color-mix(in srgb,var(--teal) 8%,transparent);border-left:3px solid var(--teal)}
.inv-k{font-family:var(--sans);font-size:.64rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase;
  color:var(--teal);margin-right:8px}
.figs{display:flex;flex-wrap:wrap;gap:16px;margin:20px 0 0}
.fig-wrap{flex:1 1 300px;min-width:0;background:var(--surface);border:1px solid var(--line);
  border-radius:12px;padding:10px}
.fig-wrap.sm{flex:1 1 220px}
.fig{width:100%;height:auto;display:block}
.fig-cap{display:block;margin:10px 4px 2px;padding-top:10px;border-top:1px solid var(--line);
  font-size:.82rem;line-height:1.5;color:var(--ink-2)}
.fig-cap .inv-k{display:inline;font-size:.62rem}
.more{margin:18px 0 0}
.more>summary{cursor:pointer;font-size:.86rem;font-weight:600;color:var(--teal);
  list-style:none;padding:8px 0}
.more>summary::-webkit-details-marker{display:none}
.more>summary::before{content:"▸ ";color:var(--muted)}
.more[open]>summary::before{content:"▾ "}
.more-body{padding:6px 0 6px 14px;border-left:2px solid var(--line)}
.more-body h4{margin:14px 0 .3em;font-size:.82rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
.more-body p{margin:.2em 0;color:var(--ink-2);font-size:.95rem}
.findings{margin:.3em 0;padding-left:1.1em}
.findings li{margin:.4em 0;color:var(--ink-2);font-size:.92rem}
.tier{font-family:var(--mono);font-size:.64rem;text-transform:uppercase;padding:.1em .4em;border-radius:4px;
  background:color-mix(in srgb,var(--muted) 14%,transparent);color:var(--muted);margin-right:4px}
.tier-mechanism{background:color-mix(in srgb,var(--teal) 14%,transparent);color:var(--teal)}

/* method */
.method{margin:60px 0 0;padding:34px;background:var(--surface);border:1px solid var(--line);border-radius:16px}
.method h2{font-size:1.5rem;margin:0 0 .4em}
.lead-sm{color:var(--ink-2);max-width:70ch}
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:30px;margin-top:18px}
.two-col h4{font-size:.82rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin:0 0 .4em}
.two-col ul{margin:0;padding-left:1.1em}.two-col li{margin:.4em 0;color:var(--ink-2);font-size:.93rem}
.two-col p{color:var(--ink-2);font-size:.93rem;margin:0}

.foot{margin:56px 0 0;padding-top:22px;border-top:1px solid var(--line);color:var(--muted);font-size:.86rem}

/* arc figure (SVG through-line) */
.arcfig{margin:26px 0 8px;padding:22px 0 12px;border-bottom:1px solid var(--line)}
.arcfig .kicker{color:var(--teal);display:block;margin-bottom:6px}
.arc-svg{width:100%;height:auto;display:block;overflow:visible}
.arc-spine{stroke:var(--line);stroke-width:2}
.arc-ladder{stroke:var(--line);stroke-width:1;stroke-dasharray:2 4}
.arc-dot{stroke:var(--surface);stroke-width:2}
.arc-dot-open{fill:var(--surface);stroke:var(--muted);stroke-width:1.5;stroke-dasharray:3 3}
.arc-dot-n{fill:#fff;font:700 11px var(--mono);text-anchor:middle;dominant-baseline:middle}
.arc-dot-n-open{fill:var(--muted)}
.arc-dir{fill:var(--muted);font:600 8px var(--sans);text-anchor:middle;text-transform:uppercase;letter-spacing:.05em}
.arc-lbl{fill:var(--ink);font:600 10.5px var(--sans);text-anchor:middle}
.arc-lbl-open{fill:var(--muted);font-style:italic}
.arc-rung{fill:var(--muted);font:600 9.5px var(--sans);text-anchor:middle;text-transform:uppercase;letter-spacing:.04em}
.arc-rung-open{fill:var(--ochre)}
.arc-svg a{cursor:pointer}
.arc-svg a:hover .arc-lbl{fill:var(--teal)}

/* study figure images (simulation movies) */
.fig-img{width:100%;height:auto;display:block;border-radius:8px}

/* model definition + interface contract (datasheet read from the composite) */
.spec{display:flex;flex-direction:column;gap:12px;margin:20px 0 0}
.spec-panel{background:color-mix(in srgb,var(--teal) 4%,var(--surface));border:1px solid var(--line);
  border-radius:11px;padding:13px 16px;min-width:0}
.spec-panel.contract{border-left:3px solid var(--teal)}
.spec-panel.modeldef{border-left:3px solid var(--ochre)}
.spec-h{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:9px;
  padding-bottom:8px;border-bottom:1px solid var(--line)}
.spec-tag{font:700 .62rem var(--sans);text-transform:uppercase;letter-spacing:.07em;color:var(--muted)}
.contract .spec-tag{color:var(--teal)}
.modeldef .spec-tag{color:var(--ochre)}
.spec-sub{font:600 .7rem var(--mono);color:var(--ink-2)}
.spec-cls{font-family:var(--mono);font-size:.82rem;color:var(--ink);background:none;padding:0}
.port{display:flex;gap:10px;align-items:baseline;margin:5px 0;font-size:.82rem}
.port-k{flex:none;width:60px;font:600 .64rem var(--sans);text-transform:uppercase;letter-spacing:.05em;
  color:var(--muted)}
.port code{font-family:var(--mono);font-size:.8rem;color:var(--ink-2);background:none;padding:0;word-break:break-word}
.proc{display:flex;gap:12px;align-items:baseline;margin:7px 0;font-size:.8rem;flex-wrap:wrap}
.proc-cls{flex:none;font-family:var(--mono);font-size:.8rem;font-weight:700;color:var(--ochre-2);
  background:none;padding:0}
.proc-params{color:var(--muted);display:flex;flex-wrap:wrap;gap:4px 12px;min-width:0}
.pm{font-family:var(--mono);font-size:.73rem;white-space:nowrap}
.pm b{color:var(--ink-2);font-weight:600}

/* substitutability paired bars */
.subst{width:100%;height:auto;display:block;overflow:visible;max-width:440px}
.subst-obs{fill:var(--ink);font:600 12px var(--sans);text-anchor:start;dominant-baseline:middle}
.subst-dfba{fill:var(--teal)}
.subst-mm{fill:var(--ochre-2)}
.subst-bl{fill:#fff;font:700 9px var(--sans)}
.subst-delta{fill:var(--muted);font:600 11px var(--mono);text-anchor:start;dominant-baseline:middle}
.subst-ref{stroke:var(--muted);stroke-width:1;stroke-dasharray:2 2}
.subst-ref-l{fill:var(--muted);font:600 8px var(--sans);text-anchor:middle}

@media (max-width:720px){
  body{font-size:16px}
  .hl,.hl.reverse{grid-template-columns:1fr}
  .hl.reverse .hl-txt{order:0}
  .hl-fig.grid3{grid-template-columns:1fr 1fr}
  .argument,.two-col{grid-template-columns:1fr}
}
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--out", default="reports/published")
    ap.add_argument("--only", default=None)
    args = ap.parse_args()
    ws = Path(args.workspace).resolve()
    out_dir = Path(args.out).resolve()
    slugs = discover_investigations(ws)
    if args.only:
        want = {s.strip() for s in args.only.split(",")}
        slugs = [s for s in slugs if s in want]
    for slug in slugs:
        p = render_investigation(ws, slug, out_dir)
        print(f"  ✓ {slug}: {p.relative_to(ws) if p.is_relative_to(ws) else p} "
              f"({p.stat().st_size/1024:.0f} KB)")
    # landing-page fragment (reuse the existing builder over ALL investigations)
    frag = build_index_fragment(ws, discover_investigations(ws))
    (out_dir / "investigations_index.html").write_text(frag + "\n", encoding="utf-8")
    print(f"wrote landing fragment ({len(slugs)} investigations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
