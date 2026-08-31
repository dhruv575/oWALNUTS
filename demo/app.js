/* oWALNUTS × Crypto Volatility — all numbers from committed study artifacts. */
"use strict";

const NS = "http://www.w3.org/2000/svg";
const COLORS = {
  owalnuts: "#3b6fb6", numpyro: "#d1731e",
  band: "#9b8fc0", median: "#6f5fa0",
  nutpie: "#37352f", pymc: "#3b6fb6",
};
const BACKEND_LABEL = { native: "oWALNUTS (Rust)", pymc: "oWALNUTS (PyMC bridge)", nutpie: "nutpie", numpyro: "NumPyro NUTS" };
const BACKEND_DOT = { native: COLORS.owalnuts, pymc: COLORS.owalnuts, nutpie: "#8a877f", numpyro: COLORS.numpyro };
const ASSET_NAMES = { BTC: "Bitcoin", ETH: "Ethereum", XRP: "XRP", BNB: "BNB", SOL: "Solana" };

const tooltip = document.getElementById("tooltip");
function showTip(html, x, y) {
  tooltip.innerHTML = html;
  tooltip.hidden = false;
  const r = tooltip.getBoundingClientRect();
  const left = Math.min(x + 14, window.innerWidth - r.width - 8);
  const top = Math.min(y + 14, window.innerHeight - r.height - 8);
  tooltip.style.left = left + "px";
  tooltip.style.top = top + "px";
}
function hideTip() { tooltip.hidden = true; }

function el(name, attrs, parent) {
  const n = document.createElementNS(NS, name);
  for (const k in attrs) n.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(n);
  return n;
}
function fmt(x, d) { return Number(x).toLocaleString("en-US", { maximumFractionDigits: d ?? 1, minimumFractionDigits: 0 }); }

fetch("data/site-data.json").then(r => r.json()).then(build).catch(err => {
  document.getElementById("overview").textContent = "Data failed to load: " + err;
});

function build(D) {
  overview(D);
  funnelHist(D.funnel);
  funnelBars(D.funnel);
  legend();
  assets(D.assets, D.cells);
  comparison(D);
}

/* ---- overview strip ---- */
function overview(D) {
  const totalT = Object.values(D.assets).reduce((a, s) => a + s.T, 0);
  const items = [
    [fmt(totalT, 0), "days of daily closes, 5 assets"],
    ["40 / 40", "cells with zero divergences"],
    ["5 / 5", "assets: fastest wall clock (native)"],
    ["z ≤ " + D.agreement.worst_z, D.agreement.pairs + " healthy cross-backend pairs agree"],
    ["v10", "kernel revision · commit " + D.meta.commit],
  ];
  document.getElementById("overview").innerHTML =
    items.map(([a, b]) => `<div><strong>${a}</strong><span>${b}</span></div>`).join("");
}

/* ---- funnel histogram + exact curve ---- */
function funnelHist(F) {
  const W = 560, H = 300, m = { l: 40, r: 10, t: 8, b: 30 };
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Histogram of the funnel scale parameter from oWALNUTS draws against the exact normal density" });
  const iw = W - m.l - m.r, ih = H - m.t - m.b;
  const x0 = -10, x1 = 10;
  const ymax = 0.15;
  const X = v => m.l + (v - x0) / (x1 - x0) * iw;
  const Y = v => m.t + ih - Math.min(v, ymax) / ymax * ih;

  for (const gy of [0.05, 0.10, 0.15]) {
    el("line", { x1: m.l, x2: W - m.r, y1: Y(gy), y2: Y(gy), class: "gridline" }, svg);
    el("text", { x: m.l - 6, y: Y(gy) + 3, "text-anchor": "end", class: "axis-label" }, svg).textContent = gy.toFixed(2);
  }
  // histogram bars (oWALNUTS draws)
  const n = F.hist.length;
  for (let i = 0; i < n; i++) {
    if (F.hist[i] <= 0) continue;
    const bx0 = X(F.edges[i]), bx1 = X(F.edges[i + 1]);
    el("rect", {
      x: bx0 + 0.4, width: Math.max(bx1 - bx0 - 0.8, 0.6),
      y: Y(F.hist[i]), height: m.t + ih - Y(F.hist[i]),
      fill: COLORS.owalnuts, "fill-opacity": "0.5",
    }, svg);
  }
  // exact N(0,9) curve
  let d = "";
  for (let i = 0; i <= 240; i++) {
    const v = x0 + (x1 - x0) * i / 240;
    const p = Math.exp(-0.5 * (v / 3) ** 2) / (3 * Math.sqrt(2 * Math.PI));
    d += (i ? "L" : "M") + X(v).toFixed(1) + " " + Y(p).toFixed(1);
  }
  el("path", { d, fill: "none", stroke: "#37352f", "stroke-width": 1.6 }, svg);
  // -5 marker
  el("line", { x1: X(-5), x2: X(-5), y1: m.t, y2: m.t + ih, class: "midline" }, svg);
  el("text", { x: X(-5) - 4, y: m.t + 12, "text-anchor": "end", class: "axis-label" }, svg).textContent = "ω = −5";
  for (const tx of [-10, -5, 0, 5, 10]) {
    el("text", { x: X(tx), y: H - 10, "text-anchor": "middle", class: "axis-label" }, svg).textContent = tx;
  }
  // hover
  const hot = el("rect", { x: m.l, y: m.t, width: iw, height: ih, fill: "transparent" }, svg);
  hot.addEventListener("mousemove", e => {
    const r = svg.getBoundingClientRect();
    const v = x0 + (e.clientX - r.left) / r.width * W > 0 ? null : null; // placeholder
    const vx = x0 + ((e.clientX - r.left) / r.width * W - m.l) / iw * (x1 - x0);
    const bin = Math.max(0, Math.min(n - 1, Math.floor((vx - x0) / (x1 - x0) * n)));
    const exact = Math.exp(-0.5 * (vx / 3) ** 2) / (3 * Math.sqrt(2 * Math.PI));
    showTip(`<b>ω ≈ ${vx.toFixed(2)}</b><br>oWALNUTS density: ${F.hist[bin].toFixed(4)}<br>exact density: ${exact.toFixed(4)}`, e.clientX, e.clientY);
  });
  hot.addEventListener("mouseleave", hideTip);
  document.getElementById("funnel-hist").appendChild(svg);
}

/* ---- funnel tail-mass bars ---- */
function funnelBars(F) {
  const rows = F.rows.filter(r => r.arm === "FN-F" || r.backend === "numpyro");
  const W = 360, H = 300, m = { l: 40, r: 8, t: 8, b: 44 };
  const iw = W - m.l - m.r, ih = H - m.t - m.b;
  const ymax = 0.06;
  const Y = v => m.t + ih - Math.min(v, ymax) / ymax * ih;
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Tail mass below minus five by sampler run; NumPyro runs are near zero, oWALNUTS runs match the exact value" });
  for (const gy of [0.02, 0.04, 0.06]) {
    el("line", { x1: m.l, x2: W - m.r, y1: Y(gy), y2: Y(gy), class: "gridline" }, svg);
    el("text", { x: m.l - 6, y: Y(gy) + 3, "text-anchor": "end", class: "axis-label" }, svg).textContent = gy.toFixed(2);
  }
  const bw = iw / rows.length;
  rows.forEach((r, i) => {
    const isOw = r.backend === "owalnuts";
    const x = m.l + i * bw + 3;
    const h = m.t + ih - Y(r.p5);
    const rect = el("rect", {
      x, width: bw - 6, y: Y(r.p5) - (r.p5 > 0 ? 0 : -1), height: Math.max(h, r.p5 > 0 ? 2 : 1.2),
      fill: isOw ? COLORS.owalnuts : COLORS.numpyro, "fill-opacity": "0.85", rx: 2,
    }, svg);
    const label = isOw ? "oW" : "NP";
    el("text", { x: x + (bw - 6) / 2, y: H - 28, "text-anchor": "middle", class: "axis-label" }, svg).textContent = label;
    el("text", { x: x + (bw - 6) / 2, y: H - 17, "text-anchor": "middle", class: "axis-label" }, svg).textContent =
      isOw ? "s" + (r.seed % 10) : "@" + r.accept;
    rect.addEventListener("mousemove", e => showTip(
      `<b>${isOw ? "oWALNUTS" : "NumPyro NUTS"}</b> seed ${r.seed}${r.accept ? " · accept " + r.accept : ""}` +
      `<br>P(ω&lt;−5) = ${r.p5.toFixed(4)} <span style="opacity:.7">(exact 0.0478)</span>` +
      `<br>divergences: ${fmt(r.div, 0)} · wall ${r.wall}s`, e.clientX, e.clientY));
    rect.addEventListener("mouseleave", hideTip);
  });
  el("line", { x1: m.l, x2: W - m.r, y1: Y(F.exact_p5), y2: Y(F.exact_p5), stroke: "#37352f", "stroke-width": 1.2, "stroke-dasharray": "2 3" }, svg);
  document.getElementById("funnel-bars").appendChild(svg);
  const npDiv = rows.filter(r => r.backend === "numpyro").reduce((a, r) => a + r.div, 0);
  document.getElementById("funnel-note").textContent =
    `NumPyro divergences across its six cells: ${fmt(npDiv, 0)}. oWALNUTS: 0.`;
}

function legend() {
  document.getElementById("funnel-legend").innerHTML =
    `<span><i class="legend-swatch" style="background:${COLORS.owalnuts}"></i>oWALNUTS (paper tuning + Appendix C adaptation)</span>` +
    `<span><i class="legend-swatch" style="background:${COLORS.numpyro}"></i>NumPyro NUTS</span>` +
    `<span><i class="legend-swatch" style="background:#37352f;height:2px"></i>exact N(0, 3²)</span>`;
}

/* ---- asset volatility cards ---- */
function assets(A, cells) {
  const grid = document.getElementById("asset-grid");
  for (const sym of ["BTC", "ETH", "XRP", "BNB", "SOL"]) {
    const s = A[sym];
    const card = document.createElement("div");
    card.className = "asset-card";
    const latest = s.mid[s.mid.length - 1];
    const nativeCells = cells.filter(c => c.asset === sym && c.cell === "native");
    const wall = Math.min(...nativeCells.map(c => c.wall));
    card.innerHTML =
      `<div class="asset-top"><span>${sym} · USDT</span><span>${s.first} → ${s.last}</span></div>` +
      `<div class="asset-name">${ASSET_NAMES[sym]} — annualized volatility, 90% band</div>` +
      `<div class="asset-chart" id="chart-${sym}"></div>` +
      `<div class="asset-bottom"><div><strong>${fmt(latest, 0)}%</strong>&nbsp;posterior median today</div>` +
      `<div>T = ${fmt(s.T, 0)} · sampled in ${wall}s</div></div>`;
    grid.appendChild(card);
    bandChart(document.getElementById("chart-" + sym), s, sym);
  }
}

function bandChart(mount, s, sym) {
  const W = 480, H = 150, m = { l: 38, r: 6, t: 6, b: 18 };
  const iw = W - m.l - m.r, ih = H - m.t - m.b;
  const n = s.dates.length;
  const ymax = Math.max(...s.hi) * 1.05;
  const X = i => m.l + i / (n - 1) * iw;
  const Y = v => m.t + ih - v / ymax * ih;
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `Posterior annualized volatility for ${sym} with 90 percent credible band` });

  const steps = ymax > 300 ? [100, 200, 300, 400] : ymax > 150 ? [50, 100, 150, 200] : [25, 50, 75, 100, 125];
  for (const gy of steps) {
    if (gy > ymax) continue;
    el("line", { x1: m.l, x2: W - m.r, y1: Y(gy), y2: Y(gy), class: "gridline" }, svg);
    el("text", { x: m.l - 5, y: Y(gy) + 3, "text-anchor": "end", class: "axis-label" }, svg).textContent = gy;
  }
  let band = "M";
  for (let i = 0; i < n; i++) band += X(i).toFixed(1) + " " + Y(s.hi[i]).toFixed(1) + " " + (i < n - 1 ? "L" : "");
  for (let i = n - 1; i >= 0; i--) band += "L" + X(i).toFixed(1) + " " + Y(s.lo[i]).toFixed(1) + " ";
  el("path", { d: band + "Z", fill: COLORS.band, "fill-opacity": "0.28" }, svg);
  let mid = "";
  for (let i = 0; i < n; i++) mid += (i ? "L" : "M") + X(i).toFixed(1) + " " + Y(s.mid[i]).toFixed(1);
  el("path", { d: mid, fill: "none", stroke: COLORS.median, "stroke-width": 1.6 }, svg);

  const ticks = [0, Math.floor(n / 3), Math.floor(2 * n / 3), n - 1];
  for (const i of ticks) {
    el("text", { x: X(i), y: H - 5, "text-anchor": i === 0 ? "start" : i === n - 1 ? "end" : "middle", class: "axis-label" }, svg).textContent = s.dates[i].slice(0, 7);
  }
  const ch = el("line", { y1: m.t, y2: m.t + ih, class: "crosshair", visibility: "hidden" }, svg);
  const dot = el("circle", { r: 3, fill: COLORS.median, stroke: "#fff", "stroke-width": 1.5, visibility: "hidden" }, svg);
  const hot = el("rect", { x: m.l, y: m.t, width: iw, height: ih, fill: "transparent" }, svg);
  hot.addEventListener("mousemove", e => {
    const r = svg.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width * W;
    const i = Math.max(0, Math.min(n - 1, Math.round((px - m.l) / iw * (n - 1))));
    ch.setAttribute("x1", X(i)); ch.setAttribute("x2", X(i)); ch.setAttribute("visibility", "visible");
    dot.setAttribute("cx", X(i)); dot.setAttribute("cy", Y(s.mid[i])); dot.setAttribute("visibility", "visible");
    showTip(`<b>${sym} · ${s.dates[i]}</b><br>median ${fmt(s.mid[i], 0)}% · 90% band ${fmt(s.lo[i], 0)}–${fmt(s.hi[i], 0)}%`, e.clientX, e.clientY);
  });
  hot.addEventListener("mouseleave", () => { hideTip(); ch.setAttribute("visibility", "hidden"); dot.setAttribute("visibility", "hidden"); });
  mount.appendChild(svg);
}

/* ---- comparison tables ---- */
function comparison(D) {
  const mount = document.getElementById("comparison");
  for (const sym of ["BTC", "ETH", "XRP", "BNB", "SOL"]) {
    const rows = D.cells.filter(c => c.asset === sym);
    const order = { native: 0, pymc: 1, nutpie: 2, numpyro: 3 };
    rows.sort((a, b) => order[a.cell] - order[b.cell] || a.seed - b.seed);
    const fastest = Math.min(...rows.map(r => r.wall));
    const div = document.createElement("div");
    div.className = "cmp-asset";
    div.innerHTML = `<div class="cmp-head"><h3>${ASSET_NAMES[sym]}</h3><span>T = ${fmt(D.assets[sym].T, 0)} days · seeds ${rows.some(r=>r.seed===97002)?"97001–97003 (oWALNUTS), 97001 (references)":"97001"}</span></div>`;
    const wrap = document.createElement("div");
    wrap.className = "table-wrap";
    wrap.innerHTML = `<table>
      <thead><tr><th>Backend</th><th>Seed</th><th>Primary gate</th><th>Globals gate</th>
      <th class="num">Min ESS</th><th class="num">ESS/s</th><th class="num">Wall (s)</th><th class="num">Div.</th></tr></thead>
      <tbody>${rows.map(r => `<tr>
        <td><span class="backend-name"><i class="backend-dot" style="background:${BACKEND_DOT[r.cell]}"></i>${BACKEND_LABEL[r.cell]}</span></td>
        <td>${r.seed}</td>
        <td><span class="pill ${r.primary ? "pass" : "fail"}">${r.primary ? "pass" : "fail"}</span></td>
        <td><span class="pill ${r.globals ? "pass" : "fail"}">${r.globals ? "pass" : "fail"}</span></td>
        <td class="num">${fmt(r.min_ess, 0)}</td>
        <td class="num">${fmt(r.ess_s, 1)}</td>
        <td class="num ${r.wall === fastest ? "fastest" : ""}">${r.wall}</td>
        <td class="num">${r.div}</td>
      </tr>`).join("")}</tbody></table>`;
    div.appendChild(wrap);
    mount.appendChild(div);
  }
}
