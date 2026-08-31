# oWALNUTS v10 versus NumPyro NUTS — three comparison gaps closed (WP14)

Preregistered (`PREREGISTRATION.md`, `protocol.json`) and run 2026-08-31 on
kernel `walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10` at `d8617a8`.
Fresh seeds 92001–92003 for every backend cell; NumPyro compile probe 92000
(non-evidence). Identical physical starts per fixture; single-thread
sequential chains on both backends; diagnostics computed by one ArviZ code
path over exported draws (`analyze.py` → `artifacts/summary.json`,
`artifacts/RESULTS.md`). Work units are labelled — oWALNUTS fused target
calls vs NumPyro leapfrog `num_steps` — and never equated. The machine was
shared with two other running agents; wall figures carry that caveat, ESS
per work unit is the robust figure.

## Part 1 — sspd-05 matched timing on v10 (T=100, contaminated fixture)

Exact `matched-timing-v1` settings (frozen shared diagonal, a=1, 500/4,000,
accept 0.9, depth 8, one thread), which measured **5.4–7.3×** bulk ESS/s on
kernel v7.

| arm | pass (9-fn gate) | pass (4-fn v1 gate, post-hoc) | wall s/seed | work/seed |
|---|---|---|---:|---:|
| T-F oWALNUTS frozen diagonal | 2/3 | 2/3 | 4.2–5.4 | 0.86–0.93M calls |
| T-I oWALNUTS adapted diagonal | 1/3 | 1/3 | 3.2–4.3 | 0.68–0.80M calls |
| T-P oWALNUTS + path block | 0/3 | 1/3 | 2.3–2.4 | 0.39–0.40M calls |
| T-N NumPyro frozen inverse mass | **3/3** | 3/3 | 21.6–30.2 | 5.9–7.0M leapfrogs |

- **Primary estimand: T-F / T-N bulk ESS per total sampling second = 4.03**
  (per functional 3.69–4.51; tail 4.12; 2/3 eligible seeds under the
  preregistered nine-functional gate; the post-hoc four-functional v1 gate
  gives the same 4.03 on the same 2 seeds). **P1 (≥3) held.**
- **ESS per work unit (labelled): T-F/T-N = 1.00.** Per fused-call vs
  per-leapfrog efficiency is at parity on this target; the 4× is execution
  throughput. NumPyro compile probe: 0.4 s implied compile (its `lax.scan`
  transcription compiles fast at T=100).
- **The v7 figure 5.4–7.3× should no longer be quoted.** Two changes moved
  it: this NumPyro transcription is faster than the v7 harness (26 s vs
  88 s per seed there), and the machine was loaded. 4× is the current,
  conservative number.
- **P2 failed:** T-F passed only 2/3 — seed 92002 has `alpha` rank R-hat
  1.0594 with bulk/tail ESS 75/23 under the nine-functional gate (the v1
  study never gated on `alpha`). The frozen-metric configuration is fragile
  on the weakly identified observation scales of this contaminated fixture.
  T-I failed on the zero-exhaustion gate (209 exhaustions on 92001, 1 on
  92002). **P3 failed:** T-P/T-I min-bulk-ESS per retained call = 2.26,
  0.51, 0.52 — the path block does **not** deliver its T=1000 advantage at
  T=100, consistent with WP4b's sspd-05 row.

## Part 2 — real-market T=48 fixture on v10 (retracts the last NumPyro win)

The pre-v9 Phase 0 pilot failed only the depth gate (3.625% caps at depth
8); the frozen NumPyro confirmation (`1ec74426…b828`) passed cleanly.

| arm | pass | max R-hat range | min bulk ESS | caps | median depth | wall s/seed |
|---|---|---|---:|---:|---:|---:|
| R-B oWALNUTS a=0.75, depth 10 | **3/3** | 1.0031–1.0053 | 848–1,189 | 0 | 5 | 0.9–1.0 |
| R-I oWALNUTS a=1, depth 10 | **3/3** | 1.0023–1.0051 | 921–1,185 | 0 | 5 | 1.0–1.1 |
| R-N NumPyro a=0.75, depth 10 | **3/3** | 1.0021–1.0046 | 1,194–1,528 | 0 | 4–5 | 5.9–6.7 |

- **P4, P5, P6 all held.** v10 + depth 10 clears the historical depth-gate
  failure with **zero** caps in 24,000 retained transitions per arm set.
- ESS/s: R-B/R-N = **3.82**, R-I/R-N = **3.17** (3/3 eligible). Per work
  unit (labelled) 0.48 / 0.41 — on this easy target NumPyro needs fewer
  leapfrogs than oWALNUTS needs target calls per effective sample; the
  wall win is throughput.

## Part 3 — Neal's funnel, NumPyro measured directly (first time)

Same 10-D funnel, starts, 2,000 warmup + 4×50,000 retained, same seeds.
Exact tail masses: P(ω<−5) = 0.0478, P(ω<−6) = 0.0228, var ω = 9.

| arm | P(ω<−5) by seed | var ω | divergences | pass | under-covers |
|---|---|---|---|---|---|
| FN-F oWALNUTS fixed paper tuning | .0510, .0461, .0476 | 8.94–9.26 | 0, 0, 0 | **3/3** | 0/3 |
| FN-A oWALNUTS Appendix C (v3 defaults) | .0498, .0439, .0428 | 8.64–9.40 | 0, 0, 0 | 2/3 | 0/3 |
| FN-N80 NumPyro accept .8 | **.0000, .0000, .0000** | 5.34–7.07 | 1391, 590, 2088 | 0/3 | **3/3** |
| FN-N95 NumPyro accept .95 | **.0000, .0000, .0115** | 5.99–8.80 | 1276, 365, 3449 | 0/3 | **3/3** |

- NumPyro's NUTS places **essentially zero mass below ω = −5** where the
  exact posterior has 4.78%, under-estimates var ω by up to 40%, and emits
  hundreds to thousands of divergences per cell — at *both* acceptance
  targets, on every seed. This is the paper's funnel claim, now measured on
  NumPyro itself rather than inferred from our no-refinement control.
  **P8, P9, P10 held** (P9's "less severely" reading: FN-N95's best cell
  reaches 0.0115 and var 8.80, closer than any FN-N80 cell).
- oWALNUTS at fixed paper tuning is exact on all three seeds with zero
  divergences (FN-F 3/3). The adaptive arm is exact on tail mass and
  variance on all seeds but missed the ω R-hat gate once (1.0102 on 92001)
  → FN-A 2/3, so **P7 failed** as stated; the same borderline-R-hat
  behaviour appeared in WP12's Stock–Watson check.
- Work at these draw counts: FN-F ≈ 8.0–8.3M calls in 4.2–4.3 s; NumPyro
  5.9–14.1M leapfrogs in 23–48 s — and the NumPyro samples are unusable
  regardless of speed.

## Verdicts for the public claims table

1. **sspd-05 timing:** supported at a corrected magnitude — ~4× bulk/tail
   ESS/s over NumPyro on the matched track (was 5.4–7.3× on v7; retire that
   figure). Per-work-unit efficiency is parity. The frozen-metric arm is
   not robust on all nine functionals (2/3) — quote the ratio with its
   eligibility.
2. **Real-market T=48:** the one comparison NumPyro used to win is
   **retracted in oWALNUTS's favour** — 3/3 at depth 10 with zero caps in
   both parameterizations and 3.2–3.8× ESS/s (per work unit 0.4–0.5×,
   labelled).
3. **Funnel:** new, strong, measured claim — NumPyro NUTS under-covers the
   funnel neck catastrophically (0 of 4.8% tail mass, 365–3,449 divergences
   per cell); oWALNUTS v10 at paper tuning is exact, zero divergences, at
   ~5× less wall. This is the headline differentiator.
4. **Path block at small T:** no advantage at T=100 (0.5–2.3× vs adapted
   diagonal) — its 2.6–3.0× gain is a T=1000 (long-path) result. Do not
   generalize it downward.

## Reproduce

```powershell
cd state_space; cargo +1.88.0-x86_64-pc-windows-gnu run --release -- --part 1_sspd05_timing --out ../artifacts/state_space --kernel-commit d8617a8
cd ../funnel;   cargo +1.88.0-x86_64-pc-windows-gnu run --release -- --preflight ../artifacts/funnel/preflight.json
python numpyro_state_space.py; python numpyro_funnel.py; python analyze.py; python checksums.py
```

Raw draws (`artifacts/*/draws/*`) are hashed in `CHECKSUMS.sha256` but not
committed (~60 MB).
