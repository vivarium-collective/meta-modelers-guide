// Render each figure composite to an SVG/PNG via bigraph-loom (headless).
//
// Drives the running workbench's loom (the actual Composite Explorer render, with
// topology + draft contracts), saving one SVG+PNG per composite under
// workspace/studies/<slug>/visualizations/ — the same files the study.yaml viz
// entries point at. These ARE loom figures (react-flow export), not a custom
// renderer.
//
// Run from a workbench worktree that has playwright installed, e.g.:
//   cd /Users/eranagmon/code/vivarium-workbench--serve-latest/vivarium_workbench/loom
//   node /Users/eranagmon/code/viva-meta-modelers-guide/scripts/render_loom_svgs.mjs
//
// Env overrides: LOOM_BASE (default http://127.0.0.1:8790), PLAYWRIGHT_FROM
// (a loom dir whose node_modules has playwright).
import { createRequire } from 'module';
import { mkdirSync, writeFileSync } from 'fs';
import { dirname } from 'path';

const PW_FROM = process.env.PLAYWRIGHT_FROM
  || '/Users/eranagmon/code/vivarium-workbench--serve-latest/vivarium_workbench/loom';
const require = createRequire(`${PW_FROM}/package.json`);
const { chromium } = require('playwright');

const BASE = process.env.LOOM_BASE || 'http://127.0.0.1:8790';
const WS = '/Users/eranagmon/code/viva-meta-modelers-guide';
const PKG = 'viva_meta_modelers_guide.composites';

// [studySlug, compositeStem]  (svg stem == compositeStem, matching study viz addrs)
const JOBS = [
  ['fig-04',   'fig04a-interaction-modalities'],
  ['fig-04',   'fig04b-cellular-interface'],
  ['fig-05',   'fig05-cell-environment'],
  ['fig-06',   'fig06-disintegration'],
  ['fig-07',   'fig07-molecular-mechanism'],
  ['fig-08',   'fig08-nested-hierarchy'],
  ['fig-09',   'fig09a-coarse-graining'],
  ['fig-09',   'fig09b-minimal-cell'],
  ['fig-10-1', 'fig10-1-division'],
  ['fig-10-2', 'fig10-2-development'],
  ['fig-10-3', 'fig10-3-evolution'],
];

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1700, height: 1200 }, deviceScaleFactor: 2 });
let ok = 0;
for (const [slug, stem] of JOBS) {
  const id = `${PKG}.${stem}`;
  const out = `${WS}/workspace/studies/${slug}/visualizations/${stem}.svg`;
  const outPng = `${WS}/workspace/studies/${slug}/visualizations/${stem}.png`;
  const url = `${BASE}/bigraph-loom/?id=${encodeURIComponent(id)}&tabs=explore,document&nopersist=1`;
  try {
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
console.log(`rendered ${ok}/${JOBS.length} loom figures`);
