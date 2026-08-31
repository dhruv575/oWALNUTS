# Preregistered sspd-11 confirmation (WP12)

Frozen 2026-08-31 before any sampling, on kernel
`walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10` at HEAD `93ed8e9`.
Program: `wiki/research-program-2026-08-31.md`. Motivation: WP4b
(`WP4B-REAL-TARGET-PATH-METRIC-V1`) passed arms I and P on the non-pathological
T=1000 fixture on one seed and required a fresh three-seed confirmation before
any product claim; the kernel has since changed (v9 → v10, WP10: recoverable
target failures refine like upstream).

## Primary: sspd-11, arms I and P, three fresh seeds

* Target, fixture (`sspd-11`, SHA-256 `2fff9766…83baad`), starts (shared,
  seed-independent, `starts/sspd-11.json`), tuning, arms I and P, functionals
  and per-run gates are exactly WP4b's (`primary/protocol.json`, copied from
  WP4b's protocol; `primary/src/main.rs` is WP4b's runner with the seed loop
  added). Arm P builds its globals block from arm I's adapted momentum
  covariance of the **same seed**, as in WP4b.
* Seeds: 91001, 91002, 91003 — verified absent (word-boundary grep) from every
  ledger, protocol and study in `oWALNUTS` and `polyscope` before this file
  was written.
* Per-run gates: rank-normalised folded split R-hat ≤ 1.01, bulk and tail ESS
  ≥ 400 on all eight functionals, zero retained divergences / invalid
  evaluations / refinement exhaustions, maximum-depth rate ≤ 1%.
* Agreement gates (arm P): every functional mean within 3 combined MCSE of
  arm I on the same seed, and of WP4b's NumPyro reference N (a=1, seed
  86001, `sspd-11-N-a1-86001.json` SHA-256 `e8587b3d…63cd6`, functionals
  `.npy` SHA-256 `5fe68ed7…376ee`; MCSE = sd/√bulk ESS recomputed with
  ArviZ 1.3 from the stored draws).
* **Confirmation rule:** an arm is *confirmed* only if all three seeds pass
  every per-run gate (and, for P, both agreement gates on every seed).
  Anything less is *not confirmed*.
* Efficiency: min over functionals of bulk ESS per retained target call;
  P/I ratio per seed, geometric mean and range. Reported, not gated.
* Preflight: zero target callbacks per arm and seed (asserted by the runner).
  Per-arm wall cap 900 s; deviations recorded here before interpretation.

Predictions (written before execution): P confirmed 3/3; I confirmed 3/3;
P/I ESS-per-call geometric mean ≥ 2; all agreement |z| ≤ 3; P median depth 6,
I median depth 8 with cap rate ≤ 1%.

## Secondary: Stock–Watson arm A on three fresh seeds

WP10 arm A (Appendix C adaptation, paper-mode v3 defaults, natural
recoverable errors, kernel v10) missed the R-hat gate by 0.0001 on its single
seed (90021). `stock_watson/` is WP10's sub-study copied verbatim (runner,
data `df90ca84…a70b4`, gates) with three arms A1–A3 identical to A except
`base_seed` 91011, 91012, 91013. Report pass rate and max R-hat per seed.
Robustness check only; no gate changed. Predictions: 2/3 or 3/3 pass; max
R-hat per seed in [1.000, 1.015]; zero divergences, invalid stops,
exhaustions and depth caps on every seed.

## Analysis

`analyze.py` (post-processing only) computes the diagnostics, gates,
agreement, efficiency ratios and writes `artifacts/summary.json`;
`checksums.py` writes `CHECKSUMS.sha256`. Raw functional draws are hashed
and not committed.
