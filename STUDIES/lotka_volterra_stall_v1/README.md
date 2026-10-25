# WP57: where the time goes in a stalled `lotka_volterra` run (`lotka_volterra_stall_v1`)

## Verdict

**Mixed. The stall is gone at the new defaults, but a different failure is
still there, and neither mitigation fixes it.**

- **No stalls at the new defaults.** 0 of 12 fresh seeds stall at `f097391c`
  (`Init::best_of(16)`). The old `Init::uniform()` failure reproduces on 4 of
  4 WP54 seeds, all hitting the 1,200 s cap.
- **The failure that remains.** 2 of 12 default seeds (5701103 and 5701106)
  each have one chain trapped in a secondary mode. These chains sit at log
  density about -430 against -137, and 139–162 reference SD off. They give
  R-hat 1.59, run 4–26x more gradients and take up to 619 s.
  `chain_warnings` names the trapped chain in every such cell.
- **Neither mitigation fixes it.** The frozen rule formally recommends
  `best_of_64` for a confirmation, but only because R1 (0 stalls) was
  satisfied by `defaults` itself.
  - `depth6_initial` traps the same two chains on the same seeds.
  - `best_of_64` cures those two seeds but traps a chain on 5701104 and
    leaves R-hat 1.039 on 5701106.
  - Both arms pass gates on 10/12 cells, the same as `defaults`.

As the frozen rule requires me to state: **this study gives no evidence that
either mitigation has a benefit.**

**The number that matters:** stalls are 0/12 at defaults and 4/4 under
`uniform`. Trapped chains are 2/12 (defaults), 1/12 (+1 marginal,
`best_of_64`) and 2/12 (`depth6_initial`).

## Where the time goes (Q2)

Telemetry was streamed from the run by the observe-only comparison observer,
one row per chain per transition. A per-call timing wrapper on the target
gives the call wall times. Two distinct mechanisms appear, and neither is the
depth cap.

| | type I: secondary-mode trap | type II: deep-tail crawl | healthy chain |
|---|---|---|---|
| where seen | 5 chains in A/B/C, plus `uniform` 5403104 chain 1 | the other 4 `uniform` stalled chains | defaults |
| start log density | -487 to -524 (best-of-16 and best-of-64 starts); -1.7e4 (uniform) | -1.2e4 to -7.6e4 | -264 to -1,178 |
| log density from t = 150 | -300 to -960 (flat) | -1.1e4 to -7.6e4 (barely moves) | -137 |
| transitions ending refinement-exhausted | **95–99.5 %** | 0.5–3 % | 0 % |
| transitions at depth cap 10 | 0.1–1.8 % | 1.7–6.4 % | 0 % |
| zero-density (rk45 failure) share of gradients | **6–43 %** | 0 % | 0.1 % |
| gradients per transition | 300–1,000 | **3,000–8,500** | 36 |
| median step | 0.005–0.02 | **1.6e-5 – 7.5e-4** | 0.10 |
| median depth | 4–6 | 6–9 | 5 |

- **Type I (secondary-mode trap).** The chain sits in a region where nearly
  every trajectory stops on refinement exhaustion, and many leaves hit the
  `rk45` `max_num_steps = 500` failure, which is a zero-density leaf. Each
  transition then pays for 8 refinement levels and barely moves. The cost is
  spread over every window, including sampling, because the chain never
  leaves.
- **Type II (deep-tail crawl).** The chain is still deep in the tail where
  the uniform start put it. Refinement goes to its maximum (selected level
  about 7, so 2^7 micro-steps per macro step) at a step of 1e-5 to 1e-3.
  Trajectories stop on U-turns at depth 6–9, so the cost is micro-steps, not
  depth caps.
- **Where the gradients go by window.** Stalled chains spend 8–38 % of their
  gradients in S1 + S2. The largest share is in S3, S4 or S5. Unfinished
  chains were at transitions 206–1,225 when the cap hit.
- **Per-gradient cost is not higher.** Against the other chains of the same
  cell, which ran at the same contention, a stalled or trapped chain's wall
  per target call is **0.52–1.08x**. That is cheaper, if anything: failing
  `rk45` calls abort early. The 1.1–3.2x against the pooled healthy median
  only reflects the heavier machine load during block T. The time goes into
  call count, not call cost.

## Detection (Q1)

- **Summary warnings.** `Summary::chain_warnings` named the trapped chain in
  5/5 completed cells with a trapped chain: WarmupStep, WarmupLogDensity,
  SampledLogDensity and RHat. It also fired spuriously on 2 healthy cells
  (5701102 under `defaults`, 5701107 under `depth6_initial`), both of which
  passed every gate. It is unavailable for timed-out runs, because errors
  return no `Posterior`.
- **Emulated WP44 rules.** The step and log-density rules, applied at the
  end of S1 to the streamed telemetry, flag every trapped and stalled chain
  (10/10).
  - The **step rule** is specific: it flagged none of the 139 healthy chains
    of blocks A–C, and one non-stalled chain in block T.
  - The **log-density rule** is not: at S1 it also flagged 26 healthy chains
    that were still converging.
- **How early.** The flag is known within **0.7–4.5 % of the wall** in the
  completed trapped cells. The lag rule (the chain has not finished S2 when
  the others have) flags at 0.8–1.2 % of the cap for two stalled `uniform`
  cells, but only at 39 % for 5403107 and 148101. In 5403107 two of four
  chains were stuck, and in 148101 a third, slow chain finished S2 last.
  P6 (identified before 25 % of wall in every stalled cell) therefore fails.

## Predictions

| | prediction | observed | held |
|---|---|---|---|
| P1 | defaults <= 2/12 stall | 0/12 | yes |
| P2 | stalled chains > 70 % of gradients in S1+S2, > 50 % depth-capped, step < 1e-3 | 8–38 % in S1+S2; cap 0–6 %; step < 1e-3 in S1+S2 on 4/5 | **no** |
| P3 | per-gradient wall > 2x healthy | 0.52–1.08x same-cell; 1.1–3.2x pooled (contended) | **no** |
| P4 | one mitigation 0/12 stalls, bit-identical where possible | 0/12 for both, but defaults was also 0/12; identity was impossible by construction on all 12 seeds for both arms | vacuous (the code scores it `true`) |
| P5 | >= 3/4 uniform targeted cells stall | 4/4 (all at the 1,200 s cap) | yes |
| P6 | every stalled chain identified before 25 % of wall | 3 of 5 stalled chains; 39–50 % on 5403107 and 148101 | **no** |

Bit-identity was impossible by construction everywhere:
- `defaults` reached initial-phase depth 7–10 on every chain of every seed,
  so the cap of 6 always binds;
- the best-of-64 starts differ on every seed.

R3 therefore reduced to max |z| <= 3: the observed maxima were 2.66 for
`best_of_64` and 2.01 for `depth6_initial`.

## Decision rule (frozen) and outcome

| arm | R1 0/12 stalls | R2 gates >= defaults (10) | R3 | rule |
|---|---|---|---|---|
| `best_of_64` | yes | 10 | yes (z max 2.66) | pass |
| `depth6_initial` | yes | 10 | yes (z max 2.01) | pass |

Both arms pass. The tie-break (fewer total gradients: 4.03M against 5.96M)
selects `best_of_64`. The "defaults never stalled" clause applies. The
gradient saving is one trapped chain fewer (0.72M against 1.83M + 0.61M),
which is a seed-level lottery, not a measured effect.

**Recommendation.**
- Do not spend a default-flip confirmation on either arm as a *stall* fix:
  the stall no longer occurs at the defaults.
- The open problem is the type I secondary-mode trap. It occurred in 5 of 36
  fresh-seed cells across the three arms, and in 2 of 12 at the defaults. It
  is visible to `chain_warnings`, and the end-of-S1 step rule sees it within
  the first few percent of the run.
- A future study should target that trap rate with many more seeds. A
  window-boundary restart of the chain flagged by the S1 step rule looks
  promising: that rule fired on 0 of 139 healthy chains here. WP33 and WP36
  rescues had problems elsewhere, so a restart would need its own
  confirmation.
- Docs: lotka's failure at the defaults is now an R-hat failure that
  `chain_warnings` names, not a timeout.

No default was changed. The only library change is the research-only opt-in
`WarmupConfig::with_initial_phase_max_depth` (commit `89c6fdf9`, default
`None`). It is unit-tested, and its no-op setting (cap 10) was smoke-checked
to give the defaults' draw hash. `cargo test` and `cargo test --features
research` pass (`artifacts/wp57-cargo-test*.log`). The fingerprints were not
touched.

## Design

The full protocol is in `PREREGISTRATION.md` and `protocol.json`, frozen at
commit `e60e4f45` before the first evidence cell.

- **Model.** `hudson_lynx_hare-lotka_volterra`. The BridgeStan library,
  data and Stan file were copied from
  `owalnuts-wt/dense-metric/STUDIES/dense_metric_posteriordb_v1/models`, a
  sibling build of the same source; the hashes are in `protocol.json`.
  Reference draws come from posteriordb `28f8d3d`.
- **Sampler.** The shipped sampler at `f097391c`, 4 chains x 1,000/1,000 on
  4 threads, with a cooperative 1,200 s cap.
- **Cells.** 40 cells, all run once in manifest order between 06:23 and
  08:29 on 2026-10-25, contended:
  - A: `defaults`, B: `best_of_64` and C: `depth6_initial`, each on fresh
    seeds 5701101–5701112;
  - T: `uniform` on 5403104, 5403107, 5403110 and 148101, declared targeted
    replications.
- **Harness check.** On the non-evidence smoke seed, the observer route
  equals plain `Sampler::run` and the `Custom` no-op route (same draw hash).
- **Gates.** House gates plus max |z| <= 4.

## Files

- `artifacts/cells/*.json`: per-cell metrics, gates, chain warnings, and the
  per-chain per-window profile (gradients, steps, depth-cap stops, stop
  reasons, refinement, selected level, zero-density count, per-gradient
  wall). They also hold the emulated WP44 flags by window.
- `artifacts/summary.json`, `artifacts/results-table.md`: the decision,
  predictions, stalled and trapped chain table, and whole-chain figures.
- `artifacts/telemetry/*.json.gz`: every transition row. The 5
  trapped-chain cells and the 4 T cells are committed. The healthy cells are
  out of git, hashed in `CHECKSUMS.sha256`. Draws are out of git.
- `artifacts/run-log.txt`, `artifacts/analyze-log.txt`, `artifacts/smoke/smoke-summary.json`.

## Anomalies and limits

- **Wall times are contended.** Per-gradient wall rose from about 420 us in
  blocks A–C to 470–1,550 us in block T. "Stall" is defined on wall time, so
  it is load-sensitive; gradient counts are the robust measure.
- **Whole-chain figures are post hoc.** The whole-chain table (stop
  fractions, zero-density share) was added after seeing the data, as
  description. The preregistered per-window profile is unchanged.
- **One analysis bug fixed.** `analyze.py` had a table-formatting bug,
  which I fixed before the final analysis; no cell was affected.

## Reproduce

```
RUSTUP_TOOLCHAIN=1.88.0-x86_64-pc-windows-gnu cargo build --release
uv venv --python 3.11 .venv && uv pip install --python .venv/Scripts/python.exe bridgestan==2.9.0 arviz==0.23.4 numpy==2.4.6 posteriordb
.venv/Scripts/python.exe run_study.py run       # resumable; never reruns a written cell
.venv/Scripts/python.exe run_study.py analyze
python checksums.py
```
