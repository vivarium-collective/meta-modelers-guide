// Render each figure composite to an SVG/PNG via bigraph-loom (headless).
//
// Drives the running workbench's loom (the actual Composite Explorer render, with
// topology + draft contracts), saving one SVG+PNG per composite under
// workspace/studies/<slug>/visualizations/ — the same files the study.yaml viz
// entries point at. These ARE loom figures (react-flow export), not a custom
// renderer.
//
// Playwright must be resolvable: either run this from a dir whose
// node_modules has `playwright` (e.g. a workbench worktree's loom/), or set
// PLAYWRIGHT_FROM=<that dir>. LOOM_BASE overrides the workbench URL.
//   PLAYWRIGHT_FROM=<workbench>/vivarium_workbench/loom node scripts/render_loom_svgs.mjs
import { createRequire } from 'module';
import { mkdirSync, writeFileSync } from 'fs';
import { dirname } from 'path';
import { fileURLToPath } from 'url';

// Repo root = the parent of this script's own directory (scripts/).
const WS = dirname(dirname(fileURLToPath(import.meta.url)));

let chromium;
try {
  ({ chromium } = await import('playwright'));
} catch {
  const from = process.env.PLAYWRIGHT_FROM;
  if (!from) {
    console.error('playwright not found — set PLAYWRIGHT_FROM=<dir with node_modules/playwright> or run from such a dir.');
    process.exit(1);
  }
  ({ chromium } = createRequire(`${from}/package.json`)('playwright'));
}

const BASE = process.env.LOOM_BASE || 'http://127.0.0.1:8790';
const PKG = process.env.LOOM_PKG || 'meta_modelers_guide.composites';

// [studySlug, compositeStem]  (svg stem == compositeStem, matching study viz addrs)
const JOBS = [
  // Fig 2 (simplified a–c): a generic process, a store hierarchy, a bio bigraph
  ['fig-01',   'fig01a-process'],
  ['fig-01',   'fig01b-store-hierarchy'],
  ['fig-01',   'fig01c-bio-bigraph'],
  ['fig-03',   'fig03a-interaction-modalities'],
  ['fig-03',   'fig03b-cellular-interface'],
  ['fig-04',   'fig04-cell-environment'],
  ['fig-05',   'fig05-disintegration'],
  ['fig-05',   'fig05b-grain-swap'],
  ['fig-06',   'fig06-molecular-mechanism'],
  ['fig-07',   'fig07-nested-hierarchy'],
  ['fig-08',   'fig08a-coarse-graining'],
  ['fig-08',   'fig08b-minimal-cell'],
  ['fig-09', 'fig09-division'],
  ['fig-10', 'fig10-development'],
  ['fig-11', 'fig11-evolution'],
  // executable compilations (fig-compilation study)
  ['fig-compilation', 'fig05-executable-coarse'],
  ['fig-compilation', 'fig05-executable-kinetic'],
  ['fig-compilation', 'fig03b-executable'],
  ['fig-compilation', 'fig04-executable'],
  ['fig-compilation', 'fig08b-executable'],
];

const ENV_JOBS = process.env.LOOM_JOBS ? JSON.parse(process.env.LOOM_JOBS) : null;
const ONLY = process.env.ONLY;  // optional: render just the composites whose stem includes this
const _JOBS = ENV_JOBS || JOBS;
const jobs = ONLY ? _JOBS.filter(([, stem]) => stem.includes(ONLY)) : _JOBS;

// Process-contract figures: show ONLY the process card, in FULL detail (contract
// + port types), no stores — Fig 4b (the cellular interface) and Fig 7 (the
// molecular mechanism). Everything else renders the full composite.
const PROC_ONLY = new Set(['fig03b-cellular-interface', 'fig06-molecular-mechanism', 'fig01a-process']);


const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1700, height: 1200 }, deviceScaleFactor: 2 });
let ok = 0;
for (const [slug, stem] of jobs) {
  const id = `${PKG}.${stem}`;
  const out = `${WS}/workspace/studies/${slug}/visualizations/${stem}.svg`;
  const outPng = `${WS}/workspace/studies/${slug}/visualizations/${stem}.png`;
  const extra = PROC_ONLY.has(stem) ? '&only=processes&detail=full&ports=types&contract=full' : '';
  const url = `${BASE}/bigraph-loom/?id=${encodeURIComponent(id)}&tabs=explore,document&nopersist=1${extra}`;
  try {
    // By default HONOR the saved default view (the aesthetic arrangement saved
    // from the Composite Explorer). Only when RESET_VIEWS=1 do we force the
    // auto "Tree" layout (mode: flow-down, empty positions) — e.g. to reset a
    // composite that has no hand-arranged view yet.
    if (process.env.RESET_VIEWS) {
      await fetch(`${BASE}/api/composite-default-view`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, view: { v: 1, mode: 'flow-down', positions: {} } }),
      }).catch(() => {});
    }
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForSelector('.react-flow__node', { timeout: 40000 });
    await page.waitForTimeout(5000);  // settle: layout + fitView + font load
    const svg = await page.evaluate(async () => {
      const fn = window.__loomExportSvg;
      return fn ? await fn() : null;
    });
    if (!svg) throw new Error('__loomExportSvg returned null');
    mkdirSync(dirname(out), { recursive: true });
    writeFileSync(out, svg, 'utf-8');
    let pngKB = 0;
    try {
      const png = await page.evaluate(async () => {
        const fn = window.__loomExportPng;
        return fn ? await fn() : null;
      });
      if (png && png.startsWith('data:image/png')) {
        const buf = Buffer.from(png.slice(png.indexOf(',') + 1), 'base64');
        writeFileSync(outPng, buf);
        pngKB = Math.round(buf.length / 1024);
      }
    } catch { /* png best-effort */ }
    console.log('OK  ', slug, stem, `(svg ${Math.round(svg.length / 1024)} KB, png ${pngKB} KB)`);
    ok++;
  } catch (e) {
    console.log('FAIL', slug, stem, String(e).split('\n')[0].slice(0, 160));
  }
}
await browser.close();
console.log(`rendered ${ok}/${jobs.length} loom figures`);
