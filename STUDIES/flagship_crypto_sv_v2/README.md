# Flagship crypto SV study v2 — closing the gates

Goal set by the user after v1: oWALNUTS should PASS the preregistered health
gates on all five assets, three fresh seeds, for both the native arm and the
`from_pymc` arm, at the v1 budget (4 chains × 3,000 retained), with no gate
weakened and no seed cherry-picked. This study is the preregistered attempt:
[PREREGISTRATION.md](PREREGISTRATION.md) (amendments A1–A7 record every
design decision, incompatibility, and mid-course correction, each dated
before the runs it affects), [protocol.json](protocol.json), evidence in
[artifacts/RESULTS.md](artifacts/RESULTS.md) and `artifacts/summary.json`,
hashes in `CHECKSUMS.sha256`.

## What changed vs v1

- **Pilot factorial** (BTC, non-evidence seeds 98000/98004, six arms):
  v1's exact configuration (O), late structured-rebuild arms via the
  `sample_chains_structured_refresh` facade driver (A: DA 0.8, B: DA 0.9),
  finer-step paper-adaptation arms (C: Γ=0.90, E: Γ=0.95), and a pooled
  rank-2 projected-arrowhead arm on a dummy-padded target (D). Selection by
  the frozen criterion — highest min{a, s, mean_h} bulk ESS with clean
  health — picked **arm E** (paper Δ=1.0, p_a=.95, Γ=0.95): the only arm to
  clear the 400 mean_h bar on any BTC pilot cell, at 3.8–5.3× v1's config on
  the ridge trio. Arm D was the best *per call* (~1.4× E) and is recorded as
  the mechanism to develop, but did not lead absolutely.
- **Python package**: `owalnuts.sample(..., refresh=...)` now exposes the
  structured-metric refresh driver to Python callables (used by the fallback
  arm), with `refresh_updates` telemetry and two new package tests.
- **pymc transport**: the compiled PyTensor gradient is not thread-safe on
  the callable transport, so pymc cells run `threads=1` (A2b) — wall is not
  comparable to 4-thread native; ESS per gradient is.
- **Extension and fallback** (A6/A7): a 4×6,000 run is inadmissible under
  the facade's hard 1e9 evaluation ceiling, so the labeled extension pools
  two independent at-budget runs (partner seeds 98011–98013) into 8-chain
  rows (`native8c`/`pymc8c`, non-stuck halves only). Cells whose chains
  stuck under the frozen one-shot metric rerun as the rebuild-enabled
  fallback (`pymcB`), reported as such.

## Results

Scorecard (a cell "passes" = primary gate AND globals gate, both preregistered,
identical for every backend; per-cell numbers in artifacts/RESULTS.md):

| asset | native at-budget | native 8c pooled (2× compute) | pymc at-budget | pymc 8c pooled | pymc fallback B | references (1 seed) |
|---|---|---|---|---|---|---|
| BTC | 0/3 | **3/3** | 1/3 | **3/3** | — | nutpie fail · NumPyro pass |
| ETH | 2/3 | **3/3** | 2/3 | — | 1/1 (heals the stuck seed) | both pass |
| XRP | **3/3** | 3/3 | **3/3** | — | — | both pass |
| BNB | 2/3 | 2/3 | 2/3 | 1/1 | — | nutpie fail · NumPyro pass |
| SOL | 0/3 (globals; primary 3/3) | **3/3** | 0/3 (stuck) | — | 3/3 primary, 1/3 globals | nutpie fail · NumPyro pass |

- **Zero divergences in all 82 oWALNUTS cells.** Every stuck pymc chain was
  healed by the preregistered rebuild fallback (primary gates pass 4/4 there).
- **At the v1 budget**, arm E lifts BTC from v1's 171–227 to 278–349 min
  primary ESS (gate 400) and passes XRP/ETH-majority/BNB-majority; the
  full 3/3-everywhere goal is met only in the labeled 2×-compute pooled tier
  (BTC, ETH, SOL, XRP) — BNB misses one pooled pair by R-hat 1.06 vs the
  1.05 globals gate, while its pymc pooled twin passes.
- **Honest residuals**: SOL pymc globals 1/3 after fallback (bulk ESS 45–181
  on the ridge pair); BNB native8c-98003 globals R-hat 1.06. Agreement:
  385/393 healthy-pair checks pass at |z| ≤ 3; the 8 exceedances (z ≤ 4.46)
  concentrate on SOL native-98013 (4 of 8), consistent with MCSE
  underestimation at ridge ESS ≈ 150 over 393 comparisons; no pair was
  excluded.
- **Strict-view**: under 1.01/400 applied to the ridge pair too, exactly one
  cell in the study passes (XRP native8c-98001) and no reference cell does
  (`globals_strict_1p01_400` in summary.json).
- **Arm D (pooled rank-2 arrowhead) generalizes per call** (pilot, seed
  98000): ETH 168/130/527 at 531k calls and SOL 125/76/1019 at 545k —
  matching arm E's at-budget results at ~60% of the work on ETH. Recorded as
  the next-phase mechanism; not in any scorecard tier (and its pilot ran on a
  3-dummy-padded target to satisfy the driver's 6-global requirement).
- **Package improvements shipped alongside**: `owalnuts.sample(refresh=...)`
  (structured-metric refresh from Python, with telemetry) and
  `from_pymc(thread_safe=True)` (per-thread compiled functions; restores
  4-thread callable-transport sampling; threads=4 vs 1 agreement-tested).

See [artifacts/RESULTS.md](artifacts/RESULTS.md) for the full per-cell table
(at-budget rows first, extension and fallback rows labeled) and
`artifacts/summary.json` for every number, including cross-backend agreement
against the frozen v1 nutpie/NumPyro reference cells (same data, same gates,
cited by hash — not rerun).

## Honest notes

- **No conditional runs anywhere**: every cell in every tier samples the full
  joint T+3 posterior (mu, a, s, h_1..h_T). Nothing is frozen during
  sampling; the fixed momentum metric is a preconditioner and does not alter
  the target. An interim status phrase "globals fixed" meant "the
  globals-gate failures were resolved (by pooling)", not conditioning; the
  arm-D pilot's three dummy coordinates were added inert N(0,1) variables
  (pilot only, no scorecard tier).

- The v1 evidence stands unreplaced: v2 adds a better-tuned configuration,
  more seeds, a compute extension, and a fallback path — all labeled.
- nutpie/NumPyro references are single-seed; oWALNUTS rows are three-seed
  with an all-seeds-must-pass reading. The demo page states this asymmetry.
- Wall times were measured on a shared machine; ESS per work unit is the
  robust figure; oWALNUTS exact fused-call counters are never merged with
  the references' leapfrog proxies.
- Raw `.f64` draws are hashed in `CHECKSUMS.sha256` but not committed;
  `.npz` functionals are committed.

## Reproduce

```powershell
cargo +1.88.0-x86_64-pc-windows-gnu build --release
python scripts/run_evidence.py E            # calibrations + native + pymc
python scripts/analyze.py                   # gates, tables, summary.json
python scripts/make_site_data.py            # demo data regeneration
python scripts/checksums.py
```

Pilot cells: `run2 <data> <out> <seed> <cal> <O|A|B|C|D|E> <label> [pilot]
[retained=<n>]`; the Python cells: `run_python_cells.py <pymc|pymcB2|nutpie|numpyro>
<SYM> <seed> [B|C|E] [pilot]`. The interpreter is
`integrations/python/.venv` (owalnuts 0.1.0b2 editable, PyMC 5.28.5,
ArviZ 0.23.4).
