/* oWALNUTS demo — all numbers from committed study artifacts (demo/build_story_data.py, demo/data/*.json). */
"use strict";

const NS = "http://www.w3.org/2000/svg";
const COLORS = {
  owalnuts: "#3b6fb6", numpyro: "#d1731e",
  band: "#9b8fc0", median: "#6f5fa0",
  nutpie: "#37352f", pymc: "#3b6fb6",
};
const BACKEND_LABEL = { native: "oWALNUTS (Rust)", native8c: "oWALNUTS (Rust, 8 chains pooled · 2× compute)", pymc: "oWALNUTS (PyMC bridge)", pymc8c: "oWALNUTS (PyMC bridge, 8 chains pooled · 2× compute)", pymcB: "oWALNUTS (PyMC bridge, fallback B)", nutpie: "nutpie", numpyro: "NumPyro NUTS" };
const BACKEND_DOT = { native: COLORS.owalnuts, native8c: COLORS.owalnuts, pymc: COLORS.owalnuts, pymc8c: COLORS.owalnuts, pymcB: COLORS.owalnuts, nutpie: "#8a877f", numpyro: COLORS.numpyro };
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

const loadJson = (path) => fetch(path).then(r => { if (!r.ok) throw new Error(path + " " + r.status); return r.json(); });
Promise.all([
  loadJson("data/site-data.json"),
  loadJson("data/story-data.json"),
  loadJson("data/funnel-orbit.json").catch(() => null),
]).then(([D, S, O]) => build(D, S, O)).catch(err => {
  document.getElementById("overview").textContent = "Data failed to load: " + err;
});

function build(D, S, O) {
  overview(D, S);
  if (O) orbitViewer(O); else document.getElementById("orbit-plot").textContent = "Orbit trace not available.";
  funnelHist(D.funnel);
  funnelBars(D.funnel);
  legend();
  funnelHonest(S.funnel_extra);
  depthCards(S.state_space);
  stateSpaceTable(S.state_space);
  realTarget(S.real_target, S.python_t1000);
  t1000Bars(S.python_t1000);
  mechanism();
  eightSchools(S.eight_schools, S.strict_track);
  assets(D.assets, D.cells);
  comparison(D);
  evidence(S.provenance, S.funnel_extra);
  retractions(S.provenance.retractions);
  footer(D.meta, S.provenance);
}

/* ---- overview strip ---- */
function overview(D, S) {
  const es = S.eight_schools.backends;
  const ow = es.find(b => b.key === "owalnuts_pymc_cfunc_t4").ess_s, np = es.find(b => b.key === "nutpie_cores4").ess_s;
  const P = S.state_space.arms.P.seeds, Q = S.state_space.arms.Q.seeds;
  const ratio = (P.reduce((a, s) => a + s.ess_per_call, 0) / P.length) / (Q.reduce((a, s) => a + s.ess_per_call, 0) / Q.length);
  const items = [
    [`${fmt(S.funnel_extra.oracle_leaves, 0)} / ${fmt(S.funnel_extra.oracle_leaves, 0)}`, "reference leaves matched to 1e-11"],
    [S.funnel_extra.v9_F50_p5.toFixed(4) + " vs " + S.funnel_extra.exact_p5.toFixed(4), "funnel tail mass, ours vs exact · NumPyro 0.0000"],
    ["≈" + fmt(Math.round(ratio / 100) * 100, 0) + "×", "ESS per gradient vs a prior-based metric, T = 1,000"],
    [(ow / 1000).toFixed(1) + "k vs " + (np / 1000).toFixed(1) + "k", "Eight Schools ESS/s from PyMC: oWALNUTS vs nutpie"],
    [`${S.provenance.preregistered_studies} · ${S.provenance.retractions.length}`, "preregistered studies · published corrections"],
  ];
  document.getElementById("overview").innerHTML =
    items.map(([a, b]) => `<div><strong>${a}</strong><span>${b}</span></div>`).join("");
}

/* ---- orbit viewer ---- */
const LEVEL_COLORS = ["#3b6fb6", "#d1731e", "#c4521f", "#a83a2a", "#7d2a3c", "#5a2050", "#3c1a5c", "#2a1a60", "#1c1a60", "#101060", "#000050"];
function levelColor(l) { return LEVEL_COLORS[Math.min(l, LEVEL_COLORS.length - 1)]; }

function orbitViewer(O) {
  const picker = document.getElementById("orbit-picker");
  const feats = O.featured;
  const titles = feats.map(f => {
    const maxL = Math.max(...f.points.map(p => p[2]));
    const s = f.start[0], a = f.accepted[0];
    const kind = maxL === 0 ? "Mouth, no refinement" : a < s - 1 ? "Dive" : a > s + 1 ? "Climb out" : "Neck";
    return `${kind} · ω ${s.toFixed(1)} → ${a.toFixed(1)}`;
  });
  feats.forEach((f, i) => {
    const b = document.createElement("button");
    b.type = "button"; b.textContent = titles[i];
    b.addEventListener("click", () => { drawOrbit(O, i); picker.querySelectorAll("button").forEach(x => x.classList.toggle("active", x === b)); });
    if (i === 0) b.classList.add("active");
    picker.appendChild(b);
  });
  const legend = document.getElementById("orbit-legend");
  const maxLevel = Math.max(...feats.flatMap(f => f.points.map(p => p[2])));
  let html = `<span><i class="legend-swatch" style="background:#c9c7c1;height:8px;width:8px;border-radius:50%"></i>retained draws</span>`;
  for (let l = 0; l <= maxLevel; l++) {
    html += `<span><i class="legend-swatch" style="background:${levelColor(l)};height:8px;width:8px;border-radius:50%"></i>level ${l} · step h/${2 ** l}</span>`;
  }
  legend.innerHTML = html;
  drawOrbit(O, 0);
}

function drawOrbit(O, idx) {
  const f = O.featured[idx];
  const plot = document.getElementById("orbit-plot"); plot.innerHTML = "";
  const W = 560, H = 420, m = { l: 40, r: 10, t: 10, b: 30 };
  const iw = W - m.l - m.r, ih = H - m.t - m.b;
  // zoom to the orbit's core: 3rd-97th percentile of x1 (coarse overshoots excluded), full omega span
    // window: the funnel region around this transition (start and accepted states); coarse
  // overshoots land far outside it and are omitted from the plane but kept in the strip.
  const anchors = [f.start, f.accepted];
  const oLo = Math.min(...anchors.map(a => a[0])), oHi = Math.max(...anchors.map(a => a[0]));
  const o0 = oLo - 2.5, o1 = oHi + 1.5;
  const half = Math.max(3 * Math.exp(o1 / 2), ...anchors.map(a => Math.abs(a[1]) * 1.3), 0.05);
  const x0 = -half, x1 = half;
  const X = v => m.l + (v - x0) / (x1 - x0) * iw;
  const Y = v => m.t + ih - (v - o0) / (o1 - o0) * ih;
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "One WALNUTS orbit on Neal's funnel, gradient evaluations coloured by refinement level" });
  const env = [];
  for (let o = o0; o <= o1; o += 0.1) env.push([o, 2 * Math.exp(o / 2)]);
  const envPath = "M" + env.map(([o, s]) => `${X(Math.max(x0, -s))},${Y(o)}`).join("L") + "L" + env.slice().reverse().map(([o, s]) => `${X(Math.min(x1, s))},${Y(o)}`).join("L") + "Z";
  el("path", { d: envPath, fill: "#f4f3ef", stroke: "none" }, svg);
  const ostep = (o1 - o0) > 6 ? 2 : 1;
  for (let o = Math.ceil(o0 / ostep) * ostep; o <= o1; o += ostep) {
    el("line", { x1: m.l, x2: W - m.r, y1: Y(o), y2: Y(o), class: "gridline" }, svg);
    el("text", { x: m.l - 6, y: Y(o) + 3, "text-anchor": "end", class: "axis-label" }, svg).textContent = "ω=" + o;
  }
  const xstep = half > 2 ? 1 : half > 0.8 ? 0.5 : half > 0.3 ? 0.2 : half > 0.1 ? 0.05 : 0.02;
  for (let x = Math.ceil(x0 / xstep) * xstep; x <= x1 + 1e-9; x += xstep) {
    el("text", { x: X(x), y: H - 8, "text-anchor": "middle", class: "axis-label" }, svg).textContent = "x₁=" + (Math.round(x * 100) / 100);
  }
  if (o0 < -5 && o1 > -5) {
    el("line", { x1: m.l, x2: W - m.r, y1: Y(-5), y2: Y(-5), stroke: "#37352f", "stroke-width": 1, "stroke-dasharray": "2 3" }, svg);
    el("text", { x: W - m.r, y: Y(-5) - 4, "text-anchor": "end", class: "axis-label" }, svg).textContent = "ω = −5 · the neck";
  }
  const g = el("g", { fill: "#c9c7c1", "fill-opacity": "0.55" }, svg);
  for (const [o, x] of O.draws) {
    if (o < o0 || o > o1 || x < x0 || x > x1) continue;
    el("circle", { cx: X(x), cy: Y(o), r: 1.4 }, g);
  }
  for (const dir of [1, -1]) {
    const pts = f.points.filter(p => p[3] === dir);
    if (!pts.length) continue;
    let d = "", prev = f.start;
    for (const p of pts) {
      const out = p[1] < x0 || p[1] > x1 || p[0] < o0 || p[0] > o1;
      if (out) { prev = p; d += ""; continue; }
      const jump = Math.abs(p[0] - prev[0]) > 1.0 || Math.abs(p[1] - prev[1]) > half * 0.6 || prev[1] < x0 || prev[1] > x1 || prev[0] < o0 || prev[0] > o1;
      d += (jump ? "M" : (d ? "L" : "M" + X(prev[1]) + "," + Y(prev[0]) + "L")) + X(p[1]) + "," + Y(p[0]);
      prev = p;
    }
    el("path", { d, fill: "none", stroke: "#37352f", "stroke-opacity": "0.35", "stroke-width": 1 }, svg);
  }
  const gp = el("g", {}, svg);
  for (const p of f.points) {
    if (p[1] < x0 || p[1] > x1 || p[0] < o0 || p[0] > o1) continue;
    const c = el("circle", { cx: X(p[1]), cy: Y(p[0]), r: p[2] > 0 ? 2.6 : 2, fill: levelColor(p[2]), "fill-opacity": p[2] > 0 ? "0.95" : "0.8", class: "orbit-pt" }, gp);
    c.addEventListener("mousemove", e => showTip(
      `<b>evaluation ${p[5]}</b> · ${p[3] > 0 ? "forward" : p[3] < 0 ? "backward" : "start"}<br>ω = ${p[0].toFixed(3)}, x₁ = ${p[1].toFixed(3)}` +
      `<br>refinement level ${p[2]} · micro step h/${2 ** p[2]} = ${(O.meta.tuning.h / 2 ** p[2]).toFixed(4)}` +
      (p[4] != null ? `<br>ΔH = ${p[4].toFixed(3)}` : ""), e.clientX, e.clientY));
    c.addEventListener("mouseleave", hideTip);
  }
  el("circle", { cx: X(f.start[1]), cy: Y(f.start[0]), r: 5, fill: "none", stroke: "#37352f", "stroke-width": 1.5 }, svg);
  el("circle", { cx: X(f.accepted[1]), cy: Y(f.accepted[0]), r: 5, fill: "#37352f" }, svg);
  el("text", { x: X(f.start[1]) + 8, y: Y(f.start[0]) - 6, class: "axis-label" }, svg).textContent = "start";
  el("text", { x: X(f.accepted[1]) + 8, y: Y(f.accepted[0]) + 12, class: "axis-label" }, svg).textContent = "accepted";
  plot.appendChild(svg);

  const strip = document.getElementById("orbit-steps"); strip.innerHTML = "";
  const SW = 360, SH = 170, sm = { l: 44, r: 6, t: 8, b: 26 };
  const siw = SW - sm.l - sm.r, sih = SH - sm.t - sm.b;
  const maxL = Math.max(1, ...f.points.map(p => p[2]));
  const ssvg = el("svg", { viewBox: `0 0 ${SW} ${SH}`, role: "img", "aria-label": "Micro step size per gradient evaluation in evaluation order" });
  const n = f.points.length;
  const SX = k => sm.l + k / Math.max(1, n - 1) * siw;
  const SY = l => sm.t + sih - (l / maxL) * sih;
  for (let l = 0; l <= maxL; l++) {
    el("line", { x1: sm.l, x2: SW - sm.r, y1: SY(l), y2: SY(l), class: "gridline" }, ssvg);
    el("text", { x: sm.l - 5, y: SY(l) + 3, "text-anchor": "end", class: "axis-label" }, ssvg).textContent = "h/" + (2 ** l);
  }
  const bw = Math.max(1, siw / n);
  f.points.forEach((p, k) => {
    el("rect", { x: SX(k) - bw / 2, y: SY(p[2]), width: bw, height: Math.max(1.5, sm.t + sih - SY(p[2])), fill: levelColor(p[2]), "fill-opacity": "0.9" }, ssvg);
  });
  const omin = o0 + 0.6, omax = o1 - 0.6;
  const OY = o => sm.t + sih - (Math.min(omax, Math.max(omin, o)) - omin) / Math.max(1e-9, omax - omin) * sih;
  el("path", { d: "M" + f.points.map((p, k) => `${SX(k)},${OY(p[0])}`).join("L"), fill: "none", stroke: "#37352f", "stroke-width": 1, "stroke-dasharray": "3 3", "stroke-opacity": "0.6" }, ssvg);
  el("text", { x: SW - sm.r, y: SH - 8, "text-anchor": "end", class: "axis-label" }, ssvg).textContent = `evaluation order → (${n} evaluations)`;
  el("text", { x: sm.l, y: SH - 8, class: "axis-label" }, ssvg).textContent = "dashed: ω along the orbit";
  strip.appendChild(ssvg);
  const refined = f.points.filter(p => p[2] > 0).length;
  document.getElementById("orbit-note").textContent =
    `Transition ${f.i}: tree depth ${f.depth}, ${fmt(f.evals, 0)} gradient evaluations, ${refined} at a refined level (finest h/${2 ** maxL}). ` +
    `Start ω = ${f.start[0].toFixed(2)}, accepted ω = ${f.accepted[0].toFixed(2)}, deepest ω visited ${Math.min(...f.points.map(p => p[0])).toFixed(2)}. ` +
    `Coarse level-0 attempts that overshoot the window are omitted from the plot but counted in the strip.`;
}

function funnelHonest(F) {
  document.getElementById("funnel-honest-text").innerHTML =
    `Our kernel v8 put <strong>${F.v8_F50_p5.toFixed(4)}</strong> of the mass below ω = −5 — twice the exact ${F.exact_p5.toFixed(4)} — ` +
    `while the authors' reference at identical tuning gave ${F.reference_R36_p5.toFixed(4)}. A ${fmt(F.oracle_leaves, 0)}-leaf differential oracle generated from the unmodified ` +
    `upstream headers disagreed with v8 on ${fmt(F.v8_disagreements, 0)} leaves and located the defect: micro-step acceptance used the path-wide max |ΔH| instead of the ` +
    `endpoint |H(end) − H(start)|, which is not symmetric under time reversal. Kernel v9 agrees with the reference on all ${fmt(F.oracle_leaves, 0)} leaves to ${F.v9_tolerance}; ` +
    `at 4 × 50,000 draws it gives P(ω &lt; −5) = ${F.v9_F50_p5.toFixed(4)}, P(ω &lt; −6) = ${F.v9_F50_p6.toFixed(4)} (exact ${F.exact_p6.toFixed(4)}), var(ω) = ${F.v9_F50_var} (exact ${F.exact_var}). ` +
    `Every v8 result on a refinement-active target was marked provisional and re-run.`;
}

/* ---- state-space depth cards + table ---- */
function depthCards(SS) {
  const grid = document.getElementById("depth-grid");
  const order = ["Q", "I", "D", "P"];
  const sub = { Q: "Prior random-walk precision only — the metric the earlier Polyscope line used", I: "Identity mass", D: "Exact posterior variances on the diagonal", P: "Cholesky of the exact tridiagonal posterior precision" };
  for (const arm of order) {
    const a = SS.arms[arm]; const s = a.seeds[0];
    const card = document.createElement("div");
    card.className = "depth-card" + (arm === "P" ? " ours" : "");
    card.innerHTML = `<div class="depth-name">${a.name.replace(" (ours)", "")}${arm === "P" ? " · ours" : ""}</div><div class="depth-sub">${sub[arm]}</div>`;
    const W = 200, H = 90, m = { l: 4, r: 4, t: 6, b: 16 };
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `Tree depth histogram for metric ${a.name}` });
    const hist = s.depth_histogram; const total = hist.reduce((x, y) => x + y, 0);
    const bw = (W - m.l - m.r) / hist.length;
    hist.forEach((c, d) => {
      const h = (c / total) * (H - m.t - m.b);
      el("rect", { x: m.l + d * bw + 1, y: H - m.b - h, width: bw - 2, height: Math.max(h, c ? 1 : 0), fill: d === SS.max_depth ? "#9b3b3b" : (arm === "P" ? COLORS.owalnuts : "#8a877f"), rx: 1 }, svg);
      el("text", { x: m.l + d * bw + bw / 2, y: H - 4, "text-anchor": "middle", class: "axis-label" }, svg).textContent = d;
    });
    card.appendChild(svg);
    const stat = document.createElement("div"); stat.className = "depth-stat";
    stat.innerHTML = `<div><strong>${(s.cap_rate * 100).toFixed(0)}%</strong><br>depth-8 caps</div><div style="text-align:right"><strong>${s.ess_per_call.toExponential(1)}</strong><br>ESS / gradient</div>`;
    card.appendChild(stat);
    grid.appendChild(card);
  }
}

function stateSpaceTable(SS) {
  const order = ["Q", "I", "D", "P"];
  const rows = [];
  for (const arm of order) for (const s of SS.arms[arm].seeds) rows.push([arm, s]);
  document.getElementById("ss-table").innerHTML = `<table>
    <thead><tr><th>Metric</th><th>Seed</th><th class="num">Median depth</th><th class="num">Cap rate</th><th class="num">Final step</th>
    <th class="num">Min bulk ESS</th><th class="num">ESS / gradient</th><th class="num">Gradients</th><th class="num">Wall (s)</th><th class="num">Mean z²</th><th class="num">Max R-hat</th></tr></thead>
    <tbody>${rows.map(([arm, s]) => `<tr${arm === "P" ? ' style="font-weight:500"' : ""}>
      <td><span class="backend-name"><i class="backend-dot" style="background:${arm === "P" ? COLORS.owalnuts : "#8a877f"}"></i>${SS.arms[arm].name}</span></td>
      <td>${s.seed}</td><td class="num">${s.median_depth}</td>
      <td class="num">${s.cap_rate ? `<span class="pill fail">${(s.cap_rate * 100).toFixed(1)}%</span>` : `<span class="pill pass">0%</span>`}</td>
      <td class="num">${s.step.toFixed(4)}</td><td class="num">${fmt(s.min_bulk_ess, 0)}</td><td class="num">${s.ess_per_call.toExponential(2)}</td>
      <td class="num">${fmt(s.calls, 0)}</td><td class="num">${s.wall.toFixed(1)}</td><td class="num">${s.mean_z2.toFixed(2)}</td><td class="num">${s.max_rhat.toFixed(4)}</td>
    </tr>`).join("")}</tbody></table>`;
}

function realTarget(R, P) {
  const g = Math.exp(R.sspd11_P_over_I_ess_per_call.reduce((a, x) => a + Math.log(x), 0) / R.sspd11_P_over_I_ess_per_call.length);
  document.getElementById("real-target-text").innerHTML =
    `The same metric on Polyscope's actual T = 1,000 model (globals free, centered coordinates, three fresh seeds): ` +
    `the posterior-precision path block gives <strong>${g.toFixed(2)}×</strong> the effective samples per gradient of the adapted diagonal ` +
    `(${R.sspd11_P_over_I_ess_per_call.map(x => x.toFixed(2)).join(", ")}), tree depth 6 instead of 8, wall ${R.sspd11_wall_P} against ${R.sspd11_wall_I}, ` +
    `and agrees with a NumPyro NUTS reference on every seed. With the globals frozen the gap is the pure path-geometry effect: ` +
    `≈${Math.round(R.frozen_globals.sspd11.FP_ess_per_call / R.frozen_globals.sspd11.FI_ess_per_call / 10) * 10}× on the regular cell and ` +
    `≈${Math.round(R.frozen_globals.sspd10.FP_ess_per_call / R.frozen_globals.sspd10.FI_ess_per_call / 10) * 10}× on the funnel-shaped cell, where the identity metric caps ` +
    `${Math.round(R.frozen_globals.sspd10.FI_caps * 100)}% of transitions and the path block caps none. ` +
    `Reported as measured: the adapted diagonal is confirmed on ${R.arm_I_confirmed}; the path block passed ${R.arm_P_confirmed} at 4 × 2,000 draws, ` +
    `and the σ<sub>x</sub> → 0 stress cell (sspd-10) is sampled correctly by no tested sampler, NumPyro included (1,510 divergences at depth 12).`;
}

function t1000Bars(P) {
  const rows = [
    ["NumPyro NUTS · identity metric · 1 thread", P.numpyro_identity_t1.ess_s, COLORS.numpyro],
    ["oWALNUTS · identity metric · 1 thread", P.native_identity_t1.ess_s, "#8a877f"],
    ["oWALNUTS · precision metric · 1 thread (Rust)", P.native_precision_t1.ess_s, COLORS.owalnuts],
    ["oWALNUTS · precision metric · numba cfunc · 1 thread", P.cfunc_precision_t1.ess_s, COLORS.owalnuts],
    ["oWALNUTS · precision metric · numba cfunc · 4 threads", P.cfunc_precision_t4.ess_s, COLORS.owalnuts],
  ];
  barChart(document.getElementById("t1000-bars"), rows, v => fmt(v, 0));
}

function barChart(mount, rows, format) {
  const max = Math.max(...rows.map(r => r[1]));
  mount.innerHTML = rows.map(([label, v, color, note]) => `<div class="bar-row">
    <div class="bar-label">${label}${note ? `<small>${note}</small>` : ""}</div>
    <div class="bar-track"><div class="bar-fill" style="width:${(v / max * 100).toFixed(1)}%;background:${color}"></div></div>
    <div class="bar-value">${format(v)}</div></div>`).join("");
}

function mechanism() {
  document.getElementById("mechanism-text").innerHTML =
    `An earlier Polyscope sampler reported 83–92% depth caps, collapsed step sizes and ESS &lt; 10 at T = 1,000 and concluded ` +
    `“any diagonal metric caps at T = 1,000”. The controlled fixture shows that was the metric, not the length: a prior-precision ` +
    `metric reproduces the pathology exactly (92% caps, step 0.003), while the identity metric in centered coordinates mixes at depth 5 ` +
    `with a condition number ≈ 13 independent of T. The T² conditioning that motivated the old line is an artefact of non-centered ` +
    `coordinates; the fix that survives on the real target is centered coordinates plus the posterior-precision path block. ` +
    `What remains open is a different problem — the σ<sub>x</sub> → 0 funnel that no Euclidean metric fixes — and it is named as such.`;
}

/* ---- throughput ---- */
function eightSchools(E, T) {
  document.getElementById("es-title").textContent = "Eight Schools from a PyMC model · min bulk ESS per second · " + E.protocol.split(";")[1].trim();
  const color = k => k.startsWith("owalnuts") ? COLORS.owalnuts : k === "numpyro" ? COLORS.numpyro : "#8a877f";
  barChart(document.getElementById("es-bars"), E.backends.map(b => [b.label, b.ess_s, color(b.key), b.note]), v => fmt(v, 0));
  document.getElementById("es-note").textContent =
    `All cells: zero divergences, max R-hat ${Math.max(...E.backends.map(b => b.max_rhat)).toFixed(4)}, posterior means agree. ` +
    `oWALNUTS work is counted as exact fused gradient calls; nutpie and NumPyro expose a leapfrog proxy. Shared laptop; nutpie's 1.1–2.6 s compile excluded from its wall.`;
  document.getElementById("strict-text").innerHTML =
    `On the strict Rust track (the same noncentered Eight Schools density, four frozen starts, 1,000/1,000, timing wrapped tightly around sampling, ` +
    `true minimum over seven seeds and six functionals) kernel v9 measures <strong>${fmt(T.owalnuts_v9_min_bulk, 0)}</strong> bulk ESS/s against ` +
    `CmdStan's ${fmt(T.cmdstan_min_bulk, 0)} — ${(T.owalnuts_v9_min_bulk / T.cmdstan_min_bulk).toFixed(2)}× — and ${fmt(T.owalnuts_v9_min_tail, 0)} tail ESS/s against BlackJAX's ` +
    `${fmt(T.blackjax_min_tail, 0)}. The figure we first published for this track, ${fmt(T.published_v7_median, 0)}, was a median over seeds labelled as a minimum; ` +
    `the like-for-like v7 minimum was ${fmt(T.like_for_like_v7_min, 0)}. The correction is in the study's release note.`;
}

/* ---- evidence ---- */
function evidence(P, F) {
  document.getElementById("evidence-grid").innerHTML = [
    [`${fmt(F.oracle_leaves, 0)} / ${fmt(F.oracle_leaves, 0)}`, `macro-step leaves generated from the Flatiron reference headers agree with kernel v9/v10 to ${F.v9_tolerance} — funnel leaves and throwing-target leaves both`],
    [`${P.preregistered_studies}`, "preregistered studies: protocol and gates frozen and hashed before a single draw; fresh seeds every time"],
    [`${P.retractions.length}`, "corrections published against our own earlier numbers, listed below with what replaced them"],
    ["0", "gate weakenings: the two-tier crypto gate is the v1 preregistration, applied identically to every backend"],
  ].map(([a, b]) => `<div class="evidence-card"><strong>${a}</strong><span>${b}</span></div>`).join("");
}

function retractions(R) {
  document.getElementById("retractions").innerHTML = `<table>
    <thead><tr><th>Claim</th><th>What we said</th><th>What is true</th><th>Where</th></tr></thead>
    <tbody>${R.map(r => `<tr><td class="wrap">${r.what}</td><td class="wrap">${r.was}</td><td class="wrap">${r.now}</td><td class="wrap mono">${r.where}</td></tr>`).join("")}</tbody></table>`;
}

function footer(meta, P) {
  document.getElementById("footer").innerHTML =
    `Kernel revision v10 · reference ${P.reference} · crypto study ${meta.study} (data through 2026-08-30, OKX daily closes) · ` +
    `${meta.seeds} · every figure from committed, checksummed artifacts · rebuilt 2026-09-01`;
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
    const order = { native: 0, native8c: 1, pymc: 2, pymc8c: 3, pymcB: 4, nutpie: 5, numpyro: 6 };
    rows.sort((a, b) => order[a.cell] - order[b.cell] || a.seed - b.seed);
    const fastest = Math.min(...rows.map(r => r.wall));
    const div = document.createElement("div");
    div.className = "cmp-asset";
    div.innerHTML = `<div class="cmp-head"><h3>${ASSET_NAMES[sym]}</h3><span>T = ${fmt(D.assets[sym].T, 0)} days · ${D.meta.seeds}</span></div>`;
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
