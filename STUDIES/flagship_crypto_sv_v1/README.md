# Flagship crypto SV study v1

Full-posterior stochastic volatility on the five largest non-stablecoin
cryptocurrencies (BTC, ETH, XRP, BNB, SOL; OKX daily closes, maximum available
history, T = 1,348–3,153), sampled by four backends on the identical density:

- **native** — oWALNUTS (Rust), paper Appendix C adaptation, one-shot
  structured precision metric (tridiagonalized 3×3 global block + AR(1)+curvature
  path block from a stage-A calibration run);
- **pymc** — the same sampler through `owalnuts.from_pymc(model, gil_free=True)`;
- **nutpie** 0.16.8 and **numpyro** 0.21.0 as external references.

Design, gates, seeds, pilots, and amendments: [PREREGISTRATION.md](PREREGISTRATION.md)
and [protocol.json](protocol.json). Evidence tables: [artifacts/RESULTS.md](artifacts/RESULTS.md)
and `artifacts/summary.json`. Figures: `figures/funnel.png` (the correctness
opener, from the frozen WP14 artifacts) and `figures/volatility.png`.
The public-facing notebook built from these artifacts lives at
`integrations/python/examples/crypto_sv.ipynb`.

## Headline results (evidence, seeds 97001–97003; full table in artifacts/RESULTS.md)

- **Zero divergences in all 40 cells, all backends, all assets.** Cross-backend
  posterior agreement holds for every healthy pair (worst z = 2.29, gate 3.0).
- **oWALNUTS native is the fastest wall on all five assets** at equal retained
  draws: XRP 13.2–15.0 s vs nutpie 15.8 s / NumPyro 29.5 s; SOL 12.8–14.6 s vs
  33.4 / 54.2 s; BNB 4.3–5.2 s vs 6.9 / 17.1 s; BTC 17.3–21.1 s vs 25.5 / 46.9 s.
- **Primary health** (R-hat ≤ 1.01, ESS ≥ 400 on μ, h_T, mean_h): oWALNUTS
  passes 3/3 seeds on XRP (native and pymc) and SOL (native), 2/3 on BNB;
  it fails on BTC and ETH at this budget (min primary ESS 99–398), where
  NumPyro passes (420–544) and nutpie passes ETH. The binding constraint
  everywhere is the (a,s) global ridge; the mature windowed adapters still
  extract ~1.5–2× more global ESS at T ≈ 3,150 than our one-shot metric.
- **Stuck seeds:** the pymc arm hit apparent local-mode trapping on
  ETH 97003 and SOL 97001/97003 (R-hat 1.44–1.65, global ESS ≤ 10, zero
  divergences/caps) with the same metric that sampled cleanly under the
  native starts — a start-sensitivity of the frozen one-shot metric, reported
  as-is.
- Predictions: P1 falsified (not every cell passes), P2 held, P3 held except
  on stuck seeds, P4 held, P5 half-held (nutpie/NumPyro lead global ESS at
  large T; oWALNUTS leads wall on 5/5), P6 held (no σ→0 boundary; posterior
  σ ≈ 0.42–0.68 across assets).

**Verdict for the demo:** the funnel correctness result plus five-asset
agreement, zero divergences, and uniformly fastest walls stand; the global
ridge at T ≈ 3,000+ is the honest open edge (global–path coupling — the
arrowhead line), and is stated as such in the notebook.

## Reproduce

```powershell
python scripts/fetch_data.py                       # refreshes data/ (network)
cargo +1.88.0-x86_64-pc-windows-gnu test           # gradient FD, lgamma, Cholesky
cargo +1.88.0-x86_64-pc-windows-gnu build --release
python scripts/run_all.py                          # calibrations + all cells (resumable)
python scripts/analyze.py                          # gates, tables, summary.json
python scripts/make_figures.py
python scripts/make_notebook.py
python scripts/checksums.py
```

The Python interpreter is `integrations/python/.venv` (owalnuts 0.1.0b2, PyMC
5.28.5, nutpie 0.16.8, NumPyro 0.21.0, ArviZ 0.23.4).

## Model

r_t ~ N(0, e^{h_t}); h_t = μ + φ(h_{t−1}−μ) + σ η_t with stationary
initialization; priors μ ~ N(−10, 5²), (φ+1)/2 ~ Beta(20, 1.5),
σ ~ HalfNormal(0.5); unconstrained coordinates [μ, a = logit((φ+1)/2),
s = ln σ, h_1..h_T]. The Rust gradient is finite-difference tested; PyMC and
the JAX transcription pass a parity check against the Rust reference
(gradients to ~4e−15) before sampling. Where the transformed density is not
representable in f64 (φ saturating at ±1), the target returns a recoverable
zero-density error and the v10 kernel refines through it.

## Honest notes

- The (a, s) global ridge (corr ≈ −0.9) bottlenecks the effective sample size
  of (φ, σ) in every backend tested; the preregistered globals gate reflects
  that shared reality and the per-backend numbers are reported side by side.
- Wall times were measured on a shared machine; ESS per work unit is the
  robust figure, and oWALNUTS work counters (exact fused calls) are never
  merged with nutpie/NumPyro leapfrog proxies.
- See PREREGISTRATION.md for amendment A1 (depth 10 → 9 at zero callbacks)
  and the pilot-phase findings that shaped the metric.
