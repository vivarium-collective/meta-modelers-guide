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
import html
import json
import re
from pathlib import Path

import yaml

TEAL = "#0d6e6b"


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


# ─── report assembly ─────────────────────────────────────────────────────────
def load_study(ws: Path, slug: str) -> dict:
    for base in (ws / "workspace" / "studies", ws / "studies"):
        p = base / slug / "study.yaml"
        if p.is_file():
            d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            d["_dir"] = p.parent
            return d
    return {}


def outcomes(study: dict) -> list[tuple[str, str]]:
    for r in study.get("runs", []):
        oc = r.get("outcomes") or {}
        if oc:
            return [(k, v.get("detail", "") if isinstance(v, dict) else str(v))
                    for k, v in oc.items()]
    return []


def study_exec_svgs(study: dict) -> list[Path]:
    d = study.get("_dir")
    if not d:
        return []
    return sorted((d / "visualizations").glob("*-dynamics.svg"))


def confidence_badge(study: dict) -> str:
    c = str(study.get("confidence") or "").strip()
    cls = {"Accepted": "ok", "Investigating": "warn", "Planned": "muted",
           "Refuted": "bad"}.get(c, "muted")
    return f'<span class="badge {cls}">{esc(c or "—")}</span>' if c else ""


def chips(pairs: list[tuple[str, str]]) -> str:
    out = []
    for k, v in pairs:
        out.append(f'<div class="chip"><span class="chip-k">{esc(k.replace("-"," "))}</span>'
                   f'<span class="chip-v">{md_inline(v)}</span></div>')
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


def study_card(study: dict, order: int, inv_map: dict) -> str:
    slug = study.get("name", "")
    title = study.get("title") or slug
    claim = study.get("claim") or ""
    oc = outcomes(study)
    svgs = study_exec_svgs(study)
    inv = inv_map.get(slug, {})
    # Figure caption BELOW the plot (publication convention): the physically-
    # checked readout for this figure, badged with its precise invariant label.
    if inv.get("invariant"):
        cap = (f'<figcaption class="fig-cap"><span class="inv-k">'
               f'{esc(_inv_label(inv.get("invariant_kind","")).upper())}</span> '
               f'{md_inline(inv.get("invariant",""))}</figcaption>')
    else:
        cap = ""
    figs = "".join(f'<figure class="fig-wrap">{inline_svg(p)}{cap}</figure>' for p in svgs)
    inv_html = ""

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
      {chips(oc)}
      {inv_html}
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
    stats = [("studies", str(len(studies))), ("executables", str(len(inv_map) or len(studies))),
             ("checked signatures", str(len(inv_map))), ("whole cell", "1")]
    stat_html = "".join(f'<div class="stat"><b>{v}</b><span>{esc(k)}</span></div>' for k, v in stats)

    # ── the arc spine
    arc = "".join(
        f'<a class="arc-node" href="#{esc(s["name"])}"><span class="arc-n">{i+1:02d}</span>'
        f'<span class="arc-t">{esc(s.get("title") or s["name"])}</span></a>'
        + ('<span class="arc-arrow">→</span>' if i < len(studies) - 1 else "")
        for i, s in enumerate(studies))

    def hl_fig(s):
        svgs = study_exec_svgs(s)
        return f'<figure class="hl-fig">{inline_svg(svgs[0])}</figure>' if svgs else ""

    def inv_line(s):
        d = inv_map.get(s.get("name", ""), {})
        return (f'<div class="invariant"><span class="inv-k">'
                f'{esc(_inv_label(d.get("invariant_kind","")).upper())}</span> '
                f'{md_inline(d.get("invariant",""))}</div>') if d.get("invariant") else ""

    # ── highlights (the interesting components, promoted)
    highlights = []
    atlas = by_slug.get("the-living-atlas")
    if atlas:
        highlights.append(f"""
        <section class="hl">
          <div class="hl-txt">
            <span class="kicker">The payoff</span>
            <h2>A cell, assembled from drafts, that lives and dies</h2>
            <p>The figures don't just each run — they <em>compose</em>. Assembled into one cell,
            it grows on a depleting nutrient (biomass peaks ≈5.1), divides once as it grows
            (cell_count 1→2), then a thermal shock ramps its temperature 37→50 °C past tolerance,
            viability collapses (1.0→0.02), and its biomass converts to molecular debris (0→4.87).
            The whole arc — grow, divide, die — in one run.</p>
            {chips(outcomes(atlas)[:4])}
            {inv_line(atlas)}
          </div>
          {hl_fig(atlas)}
        </section>""")
    three = by_slug.get("one-interface-three-mechanisms")
    if three:
        highlights.append(f"""
        <section class="hl reverse">
          <div class="hl-txt">
            <span class="kicker">The thesis, in one figure</span>
            <h2>One interface, three mechanisms</h2>
            <p>One metabolism interface — nutrients ⇒ biomass — realized three ways: a first-order
            lumped yield, saturating Michaelis–Menten kinetics, and a real COBRApy flux-balance LP.
            The compiler installs each behind the <strong>identical ports</strong>, and the three
            produce <strong>three genuinely different trajectories</strong> — biomass 4.0 (linear),
            2.67 (saturating), and 6.29 (with an acetate overflow of 30.4 on the secretions port the
            FBA solver discovers on its own). Same interface, interchangeable mechanism, distinct
            dynamics — handler independence (law 4) made runnable.</p>
            {inv_line(three)}
          </div>
          {hl_fig(three)}
        </section>""")

    # ── studies
    cards = "".join(study_card(by_slug[s], i + 1, inv_map)
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

    body = f"""
    <header class="hero">
      <span class="kicker">Executable atlas · <em>A meta-modeler's guide to the cellular interface</em></span>
      <h1>{esc(inv.get('title') or slug)}</h1>
      <p class="thesis">{md_inline(inv.get('lead') or execu.get('what_is_this') or '')}</p>
      <div class="verdict"><span class="badge ok">{esc(status or 'complete')}</span>
        <p>{md_inline(verdict)}</p></div>
      <div class="stats">{stat_html}</div>
    </header>

    <section class="intro">
      <span class="kicker">Introduction</span>
      {paras(execu.get('what_is_this') or '')}
    </section>

    <nav class="arc" aria-label="the arc">{arc}</nav>

    {''.join(highlights)}

    <section class="argument">
      <div><h3>Evidence for</h3><ul>{ef}</ul></div>
      <div><h3>Evidence against</h3><ul>{ea}</ul></div>
    </section>

    <section class="studies-wrap">
      <h2>The ten studies <span class="sub">— in arc order; claim + measured readouts + the running figure. Open a card for the full detail.</span></h2>
      {cards}
    </section>

    {shared_html}

    <footer class="foot">
      <p>Generated from <code>investigation.yaml</code> + measured readouts ·
      <a href="../dashboard/">interactive read-only workbench</a> ·
      <a href="https://github.com/vivarium-collective/viva-meta-modelers-guide">source</a></p>
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
