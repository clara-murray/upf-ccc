#!/usr/bin/env python3
"""Serve the local branded-food filter proof of concept."""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from food_filter_definitions import FILTER_CATEGORIES


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB = BASE_DIR / "branded_food_filter_metrics.sqlite3"

FACETS = {
    "ingredients": ("count_ingredient", "Number of ingredients", "ingredients"),
    "additives": ("count_additives", "Number of additives", "ingredient entries"),
    "total_sugars": ("total_sugars_g_100g", "Total sugars", "g per 100 units"),
    "saturated_fat": ("saturated_fat_g_100g", "Saturated fat", "g per 100 units"),
    "fiber": ("fiber_g_100g", "Fibre", "g per 100 units"),
    "protein": ("protein_g_100g", "Protein", "g per 100 units"),
    "vitamins": ("non_trace_vitamins", "Non-trace vitamins", "vitamins"),
}

BRAND_OWNERS = {
    "pepsico": {
        "label": "PepsiCo",
        "logo": "pepsico.svg",
        "patterns": ("%pepsico%", "pepsi-cola north america inc.", "pepsi lipton"),
    },
    "tyson": {
        "label": "Tyson Foods",
        "logo": "tyson.svg",
        "patterns": ("%tyson foods%", "tyson", "tyson tastemakers"),
    },
    "kraft_heinz": {
        "label": "Kraft Heinz",
        "logo": "kraft-heinz.svg",
        "patterns": ("%kraft heinz%", "kraft foods inc.", "kraft foods global, inc."),
    },
    "general_mills": {
        "label": "General Mills",
        "logo": "general-mills.svg",
        "patterns": ("general mills%",),
    },
    "mars": {
        "label": "Mars Inc.",
        "logo": "mars.svg",
        "patterns": ("mars, inc.", "mars chocolate north america llc", "mars retail group inc."),
    },
}

HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Branded Food Filter</title>
  <style>
    :root { color-scheme: light; --ink:#1e3e5c; --muted:#5d7283; --line:#ead8ce;
      --paper:#fff1e5; --card:#fffaf6; --accent:#b3325d; --accent-soft:#f7dce4;
      --blue:#1e558c; --light-blue:#e7f1f5; --warm-panel:#f8e8dc; }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--paper); color:var(--ink); font:15px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
    main { max-width:1120px; margin:0 auto; padding:32px 22px 56px; }
    header { margin-bottom:22px; }
    h1 { font-size:30px; letter-spacing:-.03em; margin:0 0 7px; }
    h2 { font-size:17px; margin:0; }
    p { margin:6px 0; color:var(--muted); }
    .results { display:grid; grid-template-columns:minmax(220px,.85fr) minmax(0,2fr); gap:14px; margin:22px 0; padding:14px; border-radius:18px; background:var(--warm-panel); }
    .overall-card { background:var(--blue); color:#fff; border-radius:16px; padding:22px 24px; display:flex; flex-direction:column; justify-content:center; min-height:156px; }
    .result-label { color:#d8e8f0; font-size:12px; text-transform:uppercase; letter-spacing:.09em; }
    .result-value { font-size:42px; line-height:1.05; font-weight:750; letter-spacing:-.04em; font-variant-numeric:tabular-nums; }
    #share { color:#ff9fbd; }
    .result-count { color:#d8e8f0; font-size:13px; font-variant-numeric:tabular-nums; margin-top:7px; }
    .category-results { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; }
    .category-card { border:1px solid var(--line); border-radius:13px; background:#fff; padding:15px 14px; display:flex; flex-direction:column; justify-content:space-between; min-width:0; }
    .category-heading { display:flex; align-items:center; gap:10px; min-height:40px; }
    .category-heading h2 { font-size:14px; line-height:1.2; }
    .category-icon { width:38px; height:38px; flex:0 0 38px; }
    .category-share { font-size:34px; line-height:1.05; font-weight:750; letter-spacing:-.04em; margin-top:13px; font-variant-numeric:tabular-nums; }
    .category-count { color:var(--muted); font-size:12px; margin-top:5px; font-variant-numeric:tabular-nums; }
    .owner-section { margin:0 0 22px; padding:14px; border-radius:18px; background:var(--warm-panel); }
    .owner-section h2 { margin:0 0 12px; font-size:15px; }
    .owner-results { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:10px; }
    .owner-card { min-width:0; border:1px solid var(--line); border-radius:13px; background:var(--card); padding:13px 14px; text-align:center; }
    .owner-logo { display:block; width:100%; height:42px; margin:0 auto 6px; object-fit:contain; }
    .owner-card h3 { margin:0; min-height:18px; font-size:12px; }
    .owner-share { margin-top:10px; color:var(--accent); font-size:29px; line-height:1.05; font-weight:750; font-variant-numeric:tabular-nums; }
    .owner-count { margin-top:5px; color:var(--muted); font-size:11px; font-variant-numeric:tabular-nums; }
    .summary-section { margin-top:30px; }
    .summary-heading { margin:0 0 12px; font-size:23px; letter-spacing:-.02em; }
    .summary-heading span { color:var(--accent); }
    .control-groups { display:grid; gap:22px; }
    .control-group { border:1px solid #edc4d1; border-radius:17px; padding:18px; background:#f7dce4; --accent:#b3325d; }
    .control-group.nutrient-group { border-color:#cfdee6; background:var(--light-blue); --accent:#1e558c; }
    .group-heading { margin:0 0 13px; font-size:18px; }
    .controls { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; }
    .card { background:var(--card); border:1px solid var(--line); border-radius:13px; padding:17px 18px; }
    .card-top { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:11px; }
    .range-values { display:flex; justify-content:space-between; color:var(--muted); font-size:13px; font-variant-numeric:tabular-nums; margin-bottom:6px; }
    .range-pair { position:relative; height:26px; margin:2px 5px 0; background:linear-gradient(to right,#d9ccc3 0%,#d9ccc3 100%); background-size:100% 5px; background-repeat:no-repeat; background-position:center; }
    .range-pair input[type=range] { appearance:none; -webkit-appearance:none; position:absolute; inset:0; width:100%; height:26px; margin:0; padding:0; background:transparent; pointer-events:none; }
    .range-pair input[type=range]::-webkit-slider-runnable-track { height:5px; background:transparent; }
    .range-pair input[type=range]::-moz-range-track { height:5px; background:transparent; }
    .range-pair input[type=range]::-webkit-slider-thumb { -webkit-appearance:none; appearance:none; pointer-events:auto; width:19px; height:19px; margin-top:-7px; border:2px solid #fff; border-radius:50%; background:var(--accent); box-shadow:0 0 0 1px var(--accent),0 1px 4px #0003; cursor:grab; }
    .range-pair input[type=range]::-moz-range-thumb { pointer-events:auto; width:15px; height:15px; border:2px solid #fff; border-radius:50%; background:var(--accent); box-shadow:0 0 0 1px var(--accent),0 1px 4px #0003; cursor:grab; }
    .range-pair:has(input:disabled) { opacity:.42; }
    .criterion-heading { display:flex; align-items:center; justify-content:space-between; gap:10px; }
    .criterion-title { display:flex; align-items:baseline; gap:5px; }
    .threshold { color:var(--accent); font-size:21px; font-weight:800; font-variant-numeric:tabular-nums; }
    .filter-toggle { display:flex; align-items:center; gap:7px; color:var(--muted); font-size:12px; white-space:nowrap; cursor:pointer; }
    .filter-toggle input { width:16px; height:16px; accent-color:var(--accent); cursor:pointer; }
    .filter-options { display:flex; align-items:center; justify-content:space-between; gap:12px; margin:5px 0 10px; }
    .operator-toggle { display:inline-grid; grid-template-columns:repeat(2,minmax(58px,1fr)); gap:3px; padding:3px; border-radius:9px; background:#f1e5dc; }
    .operator-toggle button { border:0; border-radius:6px; padding:6px 10px; background:transparent; color:var(--muted); font-size:11px; font-weight:700; }
    .operator-toggle button[aria-pressed="true"] { color:#fff; }
    .operator-toggle .operator-and[aria-pressed="true"] { background:#b3325d; }
    .operator-toggle .operator-or[aria-pressed="true"] { background:#1e558c; }
    .actions { display:flex; justify-content:flex-end; gap:10px; margin:20px 0 10px; }
    button { border:0; border-radius:8px; background:var(--accent); color:white; padding:9px 15px; font:600 14px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; cursor:pointer; }
    button:hover { background:#1e558c; }
    .button-secondary { background:#ead8ce; color:var(--ink); }
    #status { min-height:22px; color:var(--muted); font-size:13px; }
    .error { color:#f34d5b !important; }
    @media (max-width:900px) { .results{grid-template-columns:1fr} .overall-card{min-height:0} }
    @media (max-width:900px) { .owner-results{grid-template-columns:repeat(3,minmax(0,1fr))} }
    @media (max-width:700px) { main{padding:22px 14px 40px} .controls{grid-template-columns:1fr} .category-results{grid-template-columns:1fr} .owner-results{grid-template-columns:repeat(2,minmax(0,1fr))} .category-card{min-height:122px} .result-value{font-size:24px} }
  </style>
</head>
<body>
<main>
  <header>
    <h1>Can you define Ultra-Processed Food?</h1>
    <p>Change the sliders to find out what percent of US branded food products your definition would affect</p>
  </header>
  <div class="control-groups" aria-label="Product filters">
    <section class="control-group upf-group" aria-labelledby="group-one-heading">
      <h2 class="group-heading" id="group-one-heading">A UPF has at least...</h2>
      <div class="controls" id="controls-primary"></div>
    </section>
    <section class="control-group nutrient-group" aria-labelledby="group-two-heading">
      <h2 class="group-heading" id="group-two-heading">But should these nutrients rule it out?</h2>
      <div class="controls" id="controls-nutrition"></div>
    </section>
  </div>
  <div class="actions">
    <button id="reset" class="button-secondary" type="button">Reset filters</button>
    <button id="calculate" type="button">Calculate</button>
  </div>
  <div id="status" role="status"></div>
  <section class="summary-section" aria-live="polite">
    <h2 class="summary-heading">Your definition would include <span id="summary-share">0%</span> of all US branded foods</h2>
    <div class="results">
      <article class="overall-card">
        <div class="result-label">Total</div>
        <div class="result-value" id="share">0%</div>
        <div class="result-count" id="matching">—</div>
      </article>
      <div class="category-results" id="category-results" aria-label="Category totals"></div>
    </div>
    <section class="owner-section" aria-labelledby="owner-heading">
    <h2 id="owner-heading">How leading food companies would be impacted</h2>
      <div class="owner-results" id="owner-results" aria-label="Brand owner totals"></div>
    </section>
  </section>
</main>
<script>
const primaryControls = document.getElementById('controls-primary');
const nutritionControls = document.getElementById('controls-nutrition');
const statusEl = document.getElementById('status');
const dynamicFacets = [
  ['ingredients','ingredients',true,''],
  ['additives','additives',true,''],
  ['total_sugars','sugar',false,'%'],
  ['saturated_fat','saturated fat',false,'%'],
  ['fiber','Fibre',false,'%'],
  ['protein','Protein',false,'%'],
  ['vitamins','Non-trace vitamins',true,''],
];
const categoryIcons = {
  bread: `<svg class="category-icon" viewBox="0 0 48 48" role="img" aria-label="Bread illustration"><path d="M7 24c0-8 6-14 14-14 3 0 5 1 7 3 2-2 4-3 7-3 5 0 8 4 8 9v20H9c-1-5-2-10-2-15Z" fill="#e9b466" stroke="#aa713a" stroke-width="2"/><path d="M18 17c-2 2-3 4-3 7m13-9c-2 2-3 4-3 7m13-5c-1 2-1 4-1 6" fill="none" stroke="#f8d69b" stroke-width="3" stroke-linecap="round"/><path d="M11 33h29" stroke="#c98c4a" stroke-width="2"/></svg>`,
  biscuits: `<svg class="category-icon" viewBox="0 0 48 48" role="img" aria-label="Biscuit illustration"><circle cx="24" cy="24" r="19" fill="#e8b85e" stroke="#bd8333" stroke-width="2"/><circle cx="24" cy="24" r="14" fill="#f5d891"/><circle cx="17" cy="18" r="2" fill="#9c612e"/><circle cx="29" cy="16" r="2" fill="#9c612e"/><circle cx="32" cy="27" r="2" fill="#9c612e"/><circle cx="20" cy="31" r="2" fill="#9c612e"/><circle cx="15" cy="25" r="1.6" fill="#9c612e"/></svg>`,
  sausages: `<svg class="category-icon" viewBox="0 0 48 48" role="img" aria-label="Sausage illustration"><path d="M10 34c-3-3-2-8 2-12l10-10c4-4 9-5 12-2s2 8-2 12L22 32c-4 4-9 5-12 2Z" fill="#bd5346" stroke="#853b36" stroke-width="2"/><path d="m8 30 5 5m22-22 5 5" stroke="#f4c2a5" stroke-width="3" stroke-linecap="round"/><path d="m16 28 12-12" stroke="#df8972" stroke-width="2" stroke-linecap="round"/></svg>`,
  chips: `<svg class="category-icon" viewBox="0 0 48 48" role="img" aria-label="Crisps illustration"><path d="m10 9 28 3-3 31-23-2L10 9Z" fill="#f1c344" stroke="#bc8a20" stroke-width="2"/><path d="m12 15 24 2" stroke="#fff0ae" stroke-width="2"/><path d="M16 23c2-4 5-4 7 0l-2 8c-2 2-5 1-6-2l1-6Zm11-1c2-3 5-2 6 1l-1 8c-2 2-5 1-6-2l1-7Z" fill="#f9e7a0" stroke="#d7ad46" stroke-width="1.5"/></svg>`
};
let config;
const numberFmt = new Intl.NumberFormat('en-US');

function fmt(value, integer=false) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return '—';
  return integer ? numberFmt.format(Math.round(Number(value))) : Number(value).toFixed(1);
}
function cardFor([key,label,isInteger,suffix], section) {
  const range = config.ranges[key];
  const dataLow = range && range.minimum !== null ? Number(range.minimum) : 0;
  const dataHigh = range && range.maximum !== null ? Number(range.maximum) : dataLow;
  const low = 0;
  const high = suffix ? Math.ceil(dataHigh) : dataHigh;
  const safeHigh = high > low ? high : low + (isInteger || suffix ? 1 : 0.1);
  const step = (isInteger || suffix) ? '1' : (safeHigh > 200 ? '1' : (safeHigh < 0.1 ? '0.001' : (safeHigh < 1 ? '0.01' : '0.1')));
  const unavailable = !range || range.minimum === null || range.maximum === null;
  const card = document.createElement('article');
  card.className = 'card facet-card';
  card.dataset.key = key;
  card.dataset.integer = String(isInteger);
  card.dataset.suffix = suffix;
  card.dataset.low = String(dataLow);
  card.dataset.sliderLow = String(low);
  card.dataset.section = section;
  card.dataset.operator = 'AND';
  card.innerHTML = `
    <div class="card-top">
      <h2 class="criterion-title"><strong class="threshold">${fmt(low,isInteger || Boolean(suffix))}${suffix}</strong><span>${label}</span></h2>
    </div>
    <div class="filter-options">
      <label class="filter-toggle"><input class="filter-enabled" type="checkbox"> Include</label>
      <div class="operator-toggle" role="group" aria-label="Combine ${label} condition with earlier included conditions">
        <button type="button" class="operator-and" aria-pressed="true">And</button><button type="button" class="operator-or" aria-pressed="false">Or</button>
      </div>
    </div>
    <div class="range-values"><span class="low-label">${fmt(low,isInteger || Boolean(suffix))}${suffix}</span><span class="high-label">${fmt(high,isInteger || Boolean(suffix))}${suffix}</span></div>
    <div class="range-pair">
      <input class="minimum" type="range" min="${low}" max="${safeHigh}" step="${step}" value="${low}" aria-label="Minimum ${label}" ${unavailable?'disabled':''}>
    </div>`;
  const slider = card.querySelector('.minimum');
  const include = card.querySelector('.filter-enabled');
  const display = () => {
    const val = Number(slider.value);
    const span = Number(slider.max) - Number(slider.min) || 1;
    const position = 100 * (val - Number(slider.min)) / span;
    card.querySelector('.threshold').textContent = `${fmt(val,isInteger || Boolean(suffix))}${suffix}`;
    card.querySelector('.range-pair').style.background = `linear-gradient(to right,var(--accent) 0%,var(--accent) ${position}%,#d9ccc3 ${position}%,#d9ccc3 100%)`;
    card.querySelector('.range-pair').style.backgroundSize = '100% 5px';
    card.querySelector('.range-pair').style.backgroundRepeat = 'no-repeat';
    card.querySelector('.range-pair').style.backgroundPosition = 'center';
  };
  slider.addEventListener('input', () => {
    display();
    markDirty();
  });
  include.addEventListener('change', () => {
    slider.disabled = unavailable || !include.checked;
    markDirty();
  });
  const setOperator = operator => {
    card.dataset.operator = operator;
    card.querySelector('.operator-and').setAttribute('aria-pressed', String(operator === 'AND'));
    card.querySelector('.operator-or').setAttribute('aria-pressed', String(operator === 'OR'));
    markDirty();
  };
  card.querySelector('.operator-and').addEventListener('click', () => setOperator('AND'));
  card.querySelector('.operator-or').addEventListener('click', () => setOperator('OR'));
  slider.disabled = unavailable || !include.checked;
  display();
  return card;
}
function getFilters() {
  const criteria = [];
  document.querySelectorAll('.facet-card').forEach(card => {
    if (!card.querySelector('.filter-enabled').checked) return;
    const min = Number(card.querySelector('.minimum').value);
    criteria.push({key:card.dataset.key, min, operator:card.dataset.operator, section:card.dataset.section});
  });
  return {criteria};
}
function markDirty() {
  statusEl.textContent = 'Filters changed. Select Calculate to update the results.';
  statusEl.classList.remove('error');
}
async function updateCount() {
  const calculateButton = document.getElementById('calculate');
  calculateButton.disabled = true;
  statusEl.textContent = 'Calculating…';
  try {
    const response = await fetch('/api/count', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(getFilters())});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Could not calculate the result.');
    document.getElementById('share').textContent = `${Math.round(data.share)}%`;
    document.getElementById('summary-share').textContent = `${Math.round(data.share)}%`;
    document.getElementById('matching').textContent = `${numberFmt.format(data.matching)} / ${numberFmt.format(data.total)} products`;
    Object.entries(data.categories).forEach(([key,category]) => {
      document.getElementById(`category-${key}-share`).textContent = `${Math.round(category.share)}%`;
      document.getElementById(`category-${key}-count`).textContent = `${numberFmt.format(category.matching)} / ${numberFmt.format(category.total)} products`;
    });
    Object.entries(data.owners).forEach(([key,owner]) => {
      document.getElementById(`owner-${key}-share`).textContent = `${Math.round(owner.share)}%`;
      document.getElementById(`owner-${key}-count`).textContent = `${numberFmt.format(owner.matching)} / ${numberFmt.format(owner.total)} products`;
    });
    statusEl.textContent = '';
    statusEl.classList.remove('error');
  } catch (error) {
    statusEl.textContent = error.message;
    statusEl.classList.add('error');
  } finally {
    calculateButton.disabled = false;
  }
}
function showInitialResults() {
  document.getElementById('share').textContent = '0%';
  document.getElementById('matching').textContent = `0 / ${numberFmt.format(config.total)} products`;
  Object.entries(config.categories).forEach(([key,category]) => {
    document.getElementById(`category-${key}-share`).textContent = '0%';
    document.getElementById(`category-${key}-count`).textContent = `0 / ${numberFmt.format(category.total)} products`;
  });
  Object.entries(config.owners).forEach(([key,owner]) => {
    document.getElementById(`owner-${key}-share`).textContent = '0%';
    document.getElementById(`owner-${key}-count`).textContent = `0 / ${numberFmt.format(owner.total)} products`;
  });
}
async function init() {
  try {
    const response = await fetch('/api/config');
    config = await response.json();
    if (!response.ok) throw new Error(config.error || 'Unable to load the metrics database.');
    dynamicFacets.slice(0,4).forEach(facet => primaryControls.appendChild(cardFor(facet,'upf')));
    dynamicFacets.slice(4).forEach(facet => nutritionControls.appendChild(cardFor(facet,'exclude')));
    const categoryResults = document.getElementById('category-results');
    Object.entries(config.categories).forEach(([key,category]) => {
      const card = document.createElement('article');
      card.className = 'category-card';
      card.innerHTML = `<div class="category-heading">${categoryIcons[key]}<h2></h2></div><div class="category-count" id="category-${key}-count">—</div><div class="category-share" id="category-${key}-share">—</div>`;
      card.querySelector('h2').textContent = category.label;
      categoryResults.appendChild(card);
    });
    const ownerResults = document.getElementById('owner-results');
    Object.entries(config.owners).forEach(([key,owner]) => {
      const card = document.createElement('article');
      card.className = 'owner-card';
      card.innerHTML = `<img class="owner-logo" src="/assets/brand-logos/${owner.logo}" alt=""><h3></h3><div class="owner-share" id="owner-${key}-share">—</div><div class="owner-count" id="owner-${key}-count">—</div>`;
      card.querySelector('h3').textContent = owner.label;
      ownerResults.appendChild(card);
    });
    document.getElementById('reset').addEventListener('click', () => {
      document.querySelectorAll('.facet-card').forEach(card => {
        card.querySelector('.filter-enabled').checked = false;
        const slider = card.querySelector('.minimum');
        slider.value = card.dataset.sliderLow;
        slider.disabled = true;
        card.dataset.operator = 'AND';
        card.querySelector('.operator-and').setAttribute('aria-pressed', 'true');
        card.querySelector('.operator-or').setAttribute('aria-pressed', 'false');
        slider.dispatchEvent(new Event('input'));
      });
      markDirty();
    });
    document.getElementById('calculate').addEventListener('click', updateCount);
    showInitialResults();
  } catch (error) {
    statusEl.textContent = error.message;
    statusEl.classList.add('error');
  }
}
init();
</script>
</body>
</html>"""


class AppHandler(BaseHTTPRequestHandler):
    db_path: Path
    brand_owner_totals: dict[str, int] | None = None

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, data: dict) -> None:
        self._send(
            status,
            json.dumps(data, separators=(",", ":")).encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def _connect(self) -> sqlite3.Connection:
        uri = self.db_path.resolve().as_uri() + "?mode=ro"
        return sqlite3.connect(uri, uri=True, timeout=30)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/":
            self._send(200, HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path.startswith("/assets/brand-logos/"):
            logo_name = Path(path).name
            allowed_logos = {owner["logo"] for owner in BRAND_OWNERS.values()}
            if logo_name not in allowed_logos:
                self._json(404, {"error": "Not found"})
                return
            logo_path = BASE_DIR / "assets" / "brand-logos" / logo_name
            try:
                self._send(200, logo_path.read_bytes(), "image/svg+xml; charset=utf-8")
            except OSError:
                self._json(404, {"error": "Logo not found"})
            return
        if path != "/api/config":
            self._json(404, {"error": "Not found"})
            return
        try:
            with self._connect() as conn:
                product_count = int(
                    conn.execute("SELECT value FROM app_meta WHERE name='product_count'").fetchone()[0]
                )
                ranges = {
                    name: {"minimum": minimum, "maximum": maximum}
                    for name, minimum, maximum in conn.execute(
                        "SELECT name,minimum,maximum FROM metric_ranges"
                    )
                }
                excluded = int(conn.execute("SELECT value FROM app_meta WHERE name='excluded_outlier_products'").fetchone()[0])
                categories = {
                    key: {"label": label, "total": int(total)}
                    for key, label, total in conn.execute(
                        "SELECT category_key,label,total FROM category_totals ORDER BY rowid"
                    )
                }
                owner_totals = type(self).brand_owner_totals
                if owner_totals is None:
                    owner_expressions = []
                    owner_params = []
                    for owner in BRAND_OWNERS.values():
                        patterns = owner["patterns"]
                        predicate = " OR ".join(
                            "lower(trim(COALESCE(brand_owner,''))) LIKE ?" for _ in patterns
                        )
                        owner_expressions.append(
                            f"COALESCE(SUM(CASE WHEN ({predicate}) THEN 1 ELSE 0 END),0)"
                        )
                        owner_params.extend(patterns)
                    owner_counts = conn.execute(
                        "SELECT " + ",".join(owner_expressions) + " FROM product_metrics",
                        owner_params,
                    ).fetchone()
                    owner_totals = {
                        key: int(owner_counts[index] or 0)
                        for index, key in enumerate(BRAND_OWNERS)
                    }
                    type(self).brand_owner_totals = owner_totals
                owners = {
                    key: {
                        "label": owner["label"],
                        "logo": owner["logo"],
                        "total": owner_totals[key],
                    }
                    for key, owner in BRAND_OWNERS.items()
                }
            range_names = {"count_ingredient":"ingredients", "count_additives":"additives", "total_sugars_g_100g":"total_sugars",
                           "saturated_fat_g_100g":"saturated_fat",
                "fiber_g_100g":"fiber",
                "protein_g_100g":"protein", "non_trace_vitamins":"vitamins"}
            mapped_ranges = {range_names[k]: v for k, v in ranges.items() if k in range_names}
            self._json(200, {"total": product_count, "excluded": excluded, "ranges": mapped_ranges, "categories": categories, "owners": owners})
        except (sqlite3.Error, TypeError, IndexError) as exc:
            self._json(500, {"error": f"Could not read metrics database: {exc}"})

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/count":
            self._json(404, {"error": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > 65536:
                raise ValueError("Request is too large.")
            payload = json.loads(self.rfile.read(length) or b"{}")
            with self._connect() as conn:
                where, params = self._where_clause(payload, conn)
                total = int(conn.execute("SELECT value FROM app_meta WHERE name='product_count'").fetchone()[0])
                category_clauses = []
                category_params = []
                for key, category in FILTER_CATEGORIES.items():
                    names = tuple(name.lower() for name in category["names"])
                    placeholders = ",".join("?" for _ in names)
                    category_clauses.append(
                        f"SUM(CASE WHEN lower(trim(COALESCE(branded_food_category,''))) "
                        f"IN ({placeholders}) THEN 1 ELSE 0 END)"
                    )
                    category_params.extend(names)
                owner_clauses = []
                owner_params = []
                for owner in BRAND_OWNERS.values():
                    patterns = owner["patterns"]
                    predicate = " OR ".join(
                        "lower(trim(COALESCE(brand_owner,''))) LIKE ?" for _ in patterns
                    )
                    owner_clauses.append(
                        f"SUM(CASE WHEN ({predicate}) THEN 1 ELSE 0 END)"
                    )
                    owner_params.extend(patterns)
                result = conn.execute(
                    "SELECT COUNT(*)," + ",".join(category_clauses + owner_clauses) +
                    f" FROM product_metrics{where}",
                    category_params + owner_params + params,
                ).fetchone()
                matching = int(result[0])
                base_categories = {
                    key: int(category_total)
                    for key, category_total in conn.execute(
                        "SELECT category_key,total FROM category_totals"
                    )
                }
                categories = {}
                for index, key in enumerate(FILTER_CATEGORIES, start=1):
                    category_matching = int(result[index] or 0)
                    category_total = base_categories.get(key, 0)
                    categories[key] = {
                        "matching": category_matching,
                        "total": category_total,
                        "share": (100.0 * category_matching / category_total) if category_total else 0.0,
                    }
                base_owner_totals = type(self).brand_owner_totals
                if base_owner_totals is None:
                    base_owner_counts = conn.execute(
                        "SELECT " + ",".join(owner_clauses) + " FROM product_metrics",
                        owner_params,
                    ).fetchone()
                    base_owner_totals = {
                        key: int(base_owner_counts[offset] or 0)
                        for offset, key in enumerate(BRAND_OWNERS)
                    }
                    type(self).brand_owner_totals = base_owner_totals
                owners = {}
                first_owner_index = 1 + len(FILTER_CATEGORIES)
                for offset, (key, owner) in enumerate(BRAND_OWNERS.items()):
                    owner_matching = int(result[first_owner_index + offset] or 0)
                    owner_total = base_owner_totals[key]
                    owners[key] = {
                        "matching": owner_matching,
                        "total": owner_total,
                        "share": (100.0 * owner_matching / owner_total) if owner_total else 0.0,
                    }
            share = (100.0 * matching / total) if total else 0.0
            self._json(200, {"matching": matching, "total": total, "share": share, "categories": categories, "owners": owners})
        except (ValueError, json.JSONDecodeError) as exc:
            self._json(400, {"error": str(exc)})
        except (sqlite3.Error, TypeError, IndexError) as exc:
            self._json(500, {"error": f"Could not calculate result: {exc}"})

    @staticmethod
    def _number(value, default: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        if not math.isfinite(number):
            return default
        return number

    def _where_clause(self, payload: dict, conn: sqlite3.Connection) -> tuple[str, list[float]]:
        if not isinstance(payload, dict):
            raise ValueError("Invalid filter data.")
        groups = {"upf": [], "exclude": []}
        criteria = payload.get("criteria", [])
        if not isinstance(criteria, list) or len(criteria) > len(FACETS):
            raise ValueError("Invalid numeric filters.")
        for criterion in criteria:
            if not isinstance(criterion, dict):
                raise ValueError("Invalid filter selection.")
            key = criterion.get("key")
            operator = criterion.get("operator", "AND")
            section = criterion.get("section")
            if (
                not isinstance(key, str) or key not in FACETS
                or not isinstance(operator, str) or operator not in {"AND", "OR"}
                or not isinstance(section, str) or section not in groups
            ):
                raise ValueError("Invalid filter selection.")
            col = FACETS[key][0]
            # Clamp submitted minimum to the actual data range; column names are allow-listed above.
            meta_name = col
            row = conn.execute(
                "SELECT minimum,maximum FROM metric_ranges WHERE name=?", (meta_name,)
            ).fetchone()
            if row is None or row[0] is None or row[1] is None:
                continue
            data_min, data_max = float(row[0]), float(row[1])
            minimum = min(max(self._number(criterion.get("min"), data_min), data_min), data_max)
            groups[section].append((f"{col} >= ?", minimum, operator))

        if not groups["upf"]:
            return " WHERE 0", []

        expressions = []
        params: list[float] = []
        for section in ("upf", "exclude"):
            items = groups[section]
            if not items:
                continue
            expression = items[0][0]
            group_params = [items[0][1]]
            for clause, minimum, operator in items[1:]:
                expression = f"({expression}) {operator} ({clause})"
                group_params.append(minimum)
            if section == "exclude":
                expression = f"NOT ({expression})"
            expressions.append(f"({expression})")
            params.extend(group_params)
        where = " WHERE " + " AND ".join(expressions) if expressions else ""
        return where, params

    def log_message(self, fmt: str, *args) -> None:
        # Keep the terminal output quiet apart from startup/errors.
        return


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Metrics SQLite database")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (local-only by default)")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    db_path = args.db.resolve()
    if not db_path.is_file():
        parser.error(
            f"Metrics database not found: {db_path}\n"
            "Create it first with: python3 prepare_food_filter_metrics.py"
        )
    AppHandler.db_path = db_path
    server = ThreadingHTTPServer((args.host, args.port), AppHandler)
    print(f"Filter app running at http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping filter app.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
