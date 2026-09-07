# Benchmarks: posteriordb, Eight Schools, the funnel, and the honest position

## State of knowledge

Six preregistered posteriordb runs (17 posteriors, 4 chains, 1,000 warmup
and 1,000 retained, every sampler at its defaults) took oWALNUTS from 26 of
51 gates and 0.32x CmdStan per gradient (v1, WP22) to 42 of 51 and 0.82x per
gradient on the healthy models (v5, WP32), with more gates than CmdStan (36)
and nutpie (28) on the same seeds. The gate lead is a robustness lead: the
sampler finishes cleanly where the NUTS implementations leave a chain stuck
or divergent (`gp_pois_regr`, `arma11`, the centered eight schools,
`diamonds` against nutpie). It is not a per-gradient lead on ordinary
posteriors, and WP40 traced the remaining gap on healthy models to warmup
rather than sampling. On the strict Eight Schools track the throughput claim
survived kernel v9 at more than 2x CmdStan with hand-written gradients; on
the funnel the sampler is exact where NumPyro NUTS under-covers the neck.

## The posteriordb series

| run | ledger | oWALNUTS gates /51 | CmdStan | nutpie | ESS per gradient vs CmdStan | wall per gradient | what changed before it |
|---|---|---:|---:|---:|---|---|---|
| v1 | WP22 `posteriordb_bench_v1` | 26 | 34 | 29 | 0.32x | about 10x slower | package defaults (h0 0.1, depth 8, 4 levels); Appendix C arm froze 9 of 17 |
| v2 | WP23 `posteriordb_bench_v2` | 32 | 35 | 27 | 0.233x | 0.771x | `sampler` API, depth 10, fatal NaN made recoverable, start retries, non-`STAN_THREADS` BridgeStan build |
| v3 | WP25 `posteriordb_bench_v3` | 35 | 37 | 31 | 0.344x | 0.751x | WP24 one-sided warmup exhaustion rule (`arma11` 0/3 to 2/3, `lotka_volterra` 1/3 to 3/3) |
| v4 | WP29 `posteriordb_bench_v4` | 39/48 (incomplete) | 34/46 | 28/45 | 0.845x over 15 (0.500x without `arma11`) | 0.694x | eight refinement levels (free); Stan regularisation alone loses five gates |
| v5 | WP32 `posteriordb_bench_v5` | **42** | 36 | 28 | 1.069x all, **0.822x** healthy | **0.801x** | `MomentumSum` + Stan regularisation (post-hoc after WP31, validated here) |
| v6 | WP35 `posteriordb_bench_v6` | **45** | 34 | 29 | 0.848x on 15 fixed non-`arma11` models | 0.825x | temporary WP33 `restart_from_best` default; release rule failed (one |z| 4.02 cell, one `sblrc` process fault) |

v5 is the last breadth run admitted by its own rule and matches the shipped
defaults after WP36 restored no rescue. v6 is reported beside it as the record
of the temporary rescue default. Details of every run are in the
[ledger](../research-ledger-2026-08-31.md).

### What the series taught

- **v1 was the falsification that mattered.** Every number in the
  0.1.0-beta.2 README was true on the targets it was measured on and none of
  it generalised. Appendix C adaptation froze chains on nine of seventeen
  posteriors from uniform(-2, 2) starts.
- **The 10x wall gap was the toolchain, not the sampler.** Mingw-w64 emulates
  thread-local storage and Stan Math touches its autodiff stack on every node,
  so the `STAN_THREADS=true` BridgeStan build cost 10x per call. A non-threaded
  build plus one loaded module per thread took `arK` from 10.54 s to 1.53 s at
  identical trajectories. nutpie pays the same cost from this repository.
- **The v5 per-model picture against CmdStan per gradient**: healthy models
  0.67 to 0.95x (`earnings` 0.67, `hmm_example` 0.73, `gp_pois_regr` 0.75,
  noncentered eight schools 0.75, `arK` 0.81, `diamonds` 0.84, `nes2000` 0.85,
  `garch` 0.86, `sblrc` 0.87, `lotka_volterra` 0.88, `mesquite` 0.90, `kidiq`
  0.92, `hmm_drive_0` 0.94, `one_comp` 0.95); centered eight schools 1.18;
  `accel_gp` 0.47; `arma11` 71 (CmdStan crawled on two seeds).
- **Outright wins in v5** (gates at least equal, more ESS per gradient and per
  second): vs CmdStan on `arma11` and the centered eight schools; vs nutpie on
  `diamonds`, `arma11` and `gp_pois_regr`. ESS per second above CmdStan on 8
  of 17 models and above nutpie on 14 of 16.
- **Seed lotteries decide gates on two models.** `hmm_drive_0` draws a
  second-mode chain from uniform starts on some seeds for every sampler
  (0.02x to 134x between versions), and `lotka_volterra` starts on the `rk45`
  failure boundary freeze one chain. Neither is a kernel property, and both
  perturb whenever the first warmup transitions change.
- **Where the gap comes from is now settled** (WP30, WP34, WP40): sampling
  ESS per gradient is about 0.95x CmdStan on healthy models; the rest is
  warmup gradients (1.56x CmdStan's), from single-leaf reverse-coarser step
  crashes and an initial-phase overshoot. See
  [step-size-adaptation](step-size-adaptation.md).

## Strict Eight Schools track

- The public 0.1 claim "fastest strict-matched competitor on noncentered
  Eight Schools" survived the v9 kernel correction (WP8
  `eight_schools_v9_rebench_v1`): true conservative minimum 12,830 bulk /
  10,346 tail ESS per second, 2.04x CmdStan and 2.47x BlackJAX on tail.
- The published 19,055 / 14,494 figures were medians, not minima; the
  erratum is in `wiki/release-0.1.0-beta.2.md`. The like-for-like v7 minimum
  was 8,634 / 5,949, still ahead of every strict competitor.
- This throughput needs a hand-written gradient. With BridgeStan gradients
  (6.7 µs against 40 ns) Eight Schools ESS per second falls about 10x
  (WP15a); the per-gradient efficiency is unchanged.
- Under the 0.2 joint default the strict track is 1.29x the old default
  (WP31 C5), and the biased-progressive outer selection is worth 1.75x over
  exact multinomial on this target (WP3-1).

## Funnel

- Kernel v8 placed about twice the correct mass in the neck at the paper's
  tuning (WP2); v9 fixed it (WP6, z -0.08 at 4 x 50,000). See
  [kernel-correctness](kernel-correctness.md).
- NumPyro NUTS under-covers the neck on 6 of 6 cells (P(omega < -5) 0.0000
  on five against exact 0.0478, with 365 to 3,449 divergences per cell);
  oWALNUTS at fixed paper tuning is exact 3/3 with zero divergences (WP14).
- The sampler defaults were biased on the funnel at four refinement levels
  (half the tail mass); eight levels fixed it and became the default (WP28).
  The defaults are unbiased on the funnel, not efficient on it: one chain per
  seed adapts to a step near 0.01 and the omega R-hat sits at 1.01 to 1.04.
  Every later default study carried a funnel side check and passed it (WP31,
  WP32, WP35, WP39, WP39B).

## Other comparisons

- **sspd-05 matched timing (WP14)**: 4.03x wall over NumPyro at per-work
  parity; the v7 figure of 5.4 to 7.3x is retired. Real-market T=48 passes
  3/3 at depth 10 in both parameterisations, 3.2 to 3.8x ESS per second.
- **Python transport (WP15B, WP18)**: from PyMC through the GIL-free cfunc
  path oWALNUTS reaches 30,982 ESS per second on Eight Schools at four cores
  against nutpie's 27,754; per exact gradient the two are at parity. See
  [integrations-and-platforms](integrations-and-platforms.md).
- **Five-asset crypto stochastic volatility (WP19, WP21)**: zero divergences
  on all cells and the fastest wall on all five assets, but the global
  (a, s) ridge limits every backend; at the v1 budget the gates pass only in
  a labelled pooled 8-chain tier. Windowed adapters extract 1.5 to 2x more
  global ESS at T of about 3,000.

## The honest position (as of 2026-09-05)

WALNUTS wins where stiffness is localised: Neal's funnel, the T=1000
state-space path, `gp_pois_regr`, the centered eight schools. Where stiffness
is uniform it reduces to NUTS with the adaptive machinery as overhead. The
posteriordb gate lead is real and reproducible on fresh seeds; the per-gradient
figure on healthy models is 0.82x CmdStan warmup-included and about 0.95x
sampling-only. Any external claim should quote v5 by its rule, the strict
Eight Schools minima with the hand-gradient caveat, and the funnel result.

## Open questions

- A step statistic that removes the warmup crashes without raising the
  final step would close most of the healthy-model gap (WP40).
- `diamonds` is the one place the depth-10 cap still binds at step 0.003 to
  0.005 (WP32).
- No posteriordb v7 is needed unless an automatic cross-chain action returns
  to the defaults.
