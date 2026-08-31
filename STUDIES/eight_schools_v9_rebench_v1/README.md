# Eight Schools v9 re-benchmark (paired re-measurement of the v38 strict track)

Status: executed 2026-08-31 on kernel `walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v9`
(oWALNUTS `1666dbb`), after the WP6 endpoint-error correction. Only the oWALNUTS cells
were re-run; competitor figures are cited from the frozen v3 release package. This is a
paired re-measurement of a frozen protocol, not a fresh confirmation: seeds
100070101–100070104 are the v38 evidence seeds, reused deliberately; seeds 88001–88003
are fresh. Five timing repetitions per seed; samples were bit-identical across
repetitions in every cell.

Run: `cargo +1.88.0-x86_64-pc-windows-gnu run --release -- <seed> 5 artifacts/cell-<seed>.json`
for each seed, then `python analyze.py`.

## Headline

| kernel | seeds | aggregation | bulk ESS/s | tail ESS/s | bulk ESS/call | tail ESS/call | beats all strict competitors |
|---|---|---|---:|---:|---:|---:|---|
| v7 (v38 evidence) | paired 4 | min over functionals of seed-median | 19,054.65 | 14,494.34 | 0.01768 | 0.01356 | yes |
| v7 (v38 evidence) | paired 4 | **true min over seeds × functionals** | 8,634.35 | 5,949.29 | 0.01704 | 0.01174 | yes |
| v9 | paired 4 | min over functionals of seed-median | 15,373.43 | 11,530.33 | 0.01743 | 0.01285 | yes |
| v9 | paired 4 | **true min over seeds × functionals** | 12,830.11 | 10,345.91 | 0.01591 | 0.01240 | yes |
| v9 | fresh 3 | min over functionals of seed-median | 16,189.64 | 12,593.04 | 0.01762 | 0.01343 | yes |
| v9 | fresh 3 | true min | 15,892.97 | 12,205.76 | 0.01695 | 0.01328 | yes |
| v9 | all 7 | true min | 12,830.11 | 10,345.91 | 0.01591 | 0.01240 | yes |

Strict competitor minima from the v3 package (true minima over all eligible cells and
functionals): CmdStan 6,290.30 / 3,950.59; BlackJAX 5,644.66 / 4,195.13; NumPyro
5,240.68 / 4,049.60 bulk / tail ESS/s.

**Verdict: the public claim "fastest among strict matched competitors tested locally"
survives v9 under both aggregations.** Under the true conservative minimum over all
seven seeds and six functionals, v9 is 2.04× the best strict competitor on bulk ESS/s
(12,830 vs CmdStan 6,290) and 2.47× on tail ESS/s (10,346 vs BlackJAX 4,195).

**The published numbers were mis-described.** 19,054.65 / 14,494.34 is
`summaries.rust.across_seeds.tau.{bulk,tail}_ess_per_total_second.median` in the v38
`analysis-summary.json` (SHA-256 `1fb8c295…5e04f`): the minimum over functionals of the
across-seed *median*, while competitor figures in `validate_release.py` are true minima
over every eligible cell. The like-for-like v7 figure is 8,634.35 / 5,949.29 (seed
100070101, whose sampler wall was 0.255 s against 0.09–0.11 s on the other three seeds).
The claim held even at that figure (1.37× / 1.42× over the best competitor); the margin
was overstated. `analyze.py` reproduces the release figure from the v38 file
(`release_figure_reproduced_from_v38_file: true`).

## What the kernel change did (work-based, machine-independent)

| paired seed | work v9/v7 | bulk ESS/call v9/v7 (six functionals) | wall v9/v7 |
|---|---:|---|---:|
| 100070101 | 1.0018 | 0.87, 0.88, 0.96, 0.99, 0.86, 0.94 | 0.63 |
| 100070102 | 0.9938 | 0.92, 1.07, 1.12, 1.10, 1.06, 0.99 | 1.30 |
| 100070103 | 1.0013 | 0.95, 0.89, 0.84, 0.87, 0.95, 0.99 | 1.38 |
| 100070104 | 1.0097 | 0.93, 1.07, 1.05, 1.01, 0.95, 0.91 | 1.08 |

Paired geometric-mean ESS per target call, v9 / v7: **0.961 bulk, 0.986 tail**. Total
target calls agree to within 1% per seed. On this target the corrected kernel is
cost-neutral within seed-to-seed noise; the v9 draws are a different realisation, so
per-functional ratios scatter ±15% as expected from ESS estimator variance at ~2,000 ESS.

Posterior agreement of every v9 paired cell with its v7 cell passed the v38 rule
(|Δmean| ≤ 0.10 pooled SD + 2 pooled MCSE; |ΔSD| ≤ 0.15 pooled SD + 2 pooled MCSE) on all
six functionals. All seven v9 cells passed health: zero divergences, zero max-depth stops,
zero invalid stops, zero refinement exhaustions, rank R-hat ≤ 1.0029, min bulk ESS 1,763,
min tail ESS 1,349.

## Per-seed v9 cells

| seed | class | sampler wall s, median (min–max) | target calls | min bulk ESS | min tail ESS | max R-hat | min bulk ESS/s | min tail ESS/s | final steps |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| 100070101 | paired | 0.1608 (0.1565–0.1644) | 129,660 | 2,062.9 | 1,663.5 | 1.0016 | 12,830.1 | 10,345.9 | .178 .154 .341 .332 |
| 100070102 | paired | 0.1334 (0.1319–0.1402) | 118,838 | 2,266.1 | 1,529.2 | 1.0015 | 16,988.4 | 11,464.2 | .323 .359 .139 .271 |
| 100070103 | paired | 0.1267 (0.1243–0.1328) | 109,151 | 1,763.0 | 1,709.5 | 1.0026 | 13,911.3 | 13,488.9 | .290 .331 .330 .299 |
| 100070104 | paired | 0.1167 (0.1144–0.1175) | 108,803 | 1,964.5 | 1,348.7 | 1.0029 | 16,835.6 | 11,558.5 | .311 .312 .290 .328 |
| 88001 | fresh | 0.1259 (0.1233–0.1334) | 115,660 | 2,038.0 | 1,536.5 | 1.0020 | 16,189.6 | 12,205.8 | .261 .298 .242 .328 |
| 88002 | fresh | 0.1218 (0.1216–0.1234) | 113,880 | 2,187.3 | 1,692.9 | 1.0015 | 17,951.1 | 13,893.6 | .358 .225 .280 .270 |
| 88003 | fresh | 0.1220 (0.1203–0.1257) | 114,376 | 1,938.3 | 1,535.8 | 1.0006 | 15,893.0 | 12,593.0 | .190 .253 .294 .317 |

## Load caveat

Three other agents were running Rust builds and MCMC on this 16-core machine during
execution. Wall times are therefore upper bounds on cost; the v9 walls (0.117–0.161 s)
are 8–38% above the three fast v7 walls (0.092–0.108 s) with identical target-call
counts, which is consistent with load rather than kernel cost. ESS per target call is the
primary robustness figure; the wall-based ESS/s numbers above are conservative for v9.

## Files

`protocol.json`, `PREREGISTRATION.md`, `src/main.rs`, `analyze.py`, `artifacts/cell-*.json`,
`artifacts/summary.json`, `artifacts/RESULTS.md`, `RELEASE-NOTE.md`, `CHECKSUMS.sha256`.
