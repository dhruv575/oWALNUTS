# Latest WAL build versus conservative NUTS

The latest build does **not** unlock a large speedup on this hierarchical
binomial workload. Across 36 paired runs, installed-WAL/new-WAL sampling-time
ratios had median 1.018 (range .988–1.044); every pair produced bit-identical
draws. This small timing difference is not evidence of a major improvement.

The comparison rebuilt commit e7139bed in release mode with locked dependencies,
used distinct hash-verified native extensions, and held targets, starts, seeds,
budgets and execution conditions fixed. All confirmation fits ran serially on
one pinned CPU. NUTS used nutpie0.16.11 and target acceptance .999; WAL used .9.
Both used four chains, 1000 warmup and depth11. Sampling time includes warmup.
Full worker time includes imports, diagnostics and raw-draw compression.

## Frozen noncentered comparison: 108 fits

Three synthetic cases: the existing mixed-data case, plus deterministic 10x and
100x replication of counts in groups with original n>=1000. These strengthen
the information imbalance, not necessarily every notion of funnel difficulty.
They are not independent observed datasets. Independent references passed all
resolution/domain checks, without using either sampler as ground truth.

Each cell below is full-gate passes out of four seeds, followed by median
sampling seconds. Installed WAL had exactly the same passes as rebuilt WAL.

| Case | Engine | 4000 draws | 8000 draws | 16000 draws |
|---|---|---|---|---|
| Original mixed | NUTS | 3/4; .710s | 3/4; 1.258s | 3/4; 2.347s |
| Original mixed | Rebuilt WAL | 3/4; .501s | 4/4; .802s | 4/4; 1.413s |
| Concentration 10x | NUTS | 1/4; 1.170s | 4/4; 2.101s | 4/4; 3.939s |
| Concentration 10x | Rebuilt WAL | 3/4; 1.282s | 4/4; 1.951s | 4/4; 3.326s |
| Concentration 100x | NUTS | 0/4; 2.210s | 1/4; 3.956s | 2/4; 7.480s |
| Concentration 100x | Rebuilt WAL | 2/4; 4.542s | 4/4; 6.851s | 3/4; 11.451s |

Zero divergences/depth hits, Rhat/ESS, reference mean accuracy and MCSE are
separate gates. The persistent original-case NUTS failure had one divergence.
The two 16000-draw concentrated-case NUTS failures hit depth11, despite passing
accuracy and precision checks. The concentrated WAL failure at 16000 had no
divergences/depth hits but failed health/precision gates. Longer runs do not
guarantee a pass; preserve these failures rather than choosing a favorable row.

For the predefined budget ladder, NUTS reached a passing run for 3/4, 4/4 and
2/4 seeds across the three cases; WAL did for 4/4 in each. Cumulative sampling
costs for WAL were [.635, .485, .455, 1.346]s; [1.286, 1.329, 1.277, 3.177]s;
and [10.894, 4.722, 9.922, 4.851]s. NUTS costs, including spent costs for
censored runs marked C, were [4.316 C, .675, .727, .710]s;
[3.229, 1.188, 3.426, 3.146]s; [5.798, 13.615, 13.677 C, 16.695 C]s.
These are exploratory time-to-gate observations, not a universal speed ratio.
Repeated checking against a known reference is itself a benchmark procedure,
not an available production stopping rule or a calibrated coverage guarantee.

## Post-hoc hybrid control: 24 fits

Center the data-rich groups and noncenter the sparse groups. Keep the same
seeds, 8000 draws and other settings. This was declared after partial main
results and before inspecting mixed100 results; it needs fresh replication.

| Case | NUTS pass / sampling | Rebuilt WAL pass / sampling | Worker medians, NUTS / WAL |
|---|---|---|---|
| Original mixed | 0/4; 3.497s | 0/4; 1.045s | 6.054s / 3.604s |
| Concentration 10x | 4/4; .845s | 4/4; .604s | 3.395s / 3.150s |
| Concentration 100x | 4/4; .803s | 4/4; 1.440s | 3.345s / 3.986s |

The rewrite helps both samplers on concentrated data and hurts both on the
original dataset. At 10x, WAL is about1.40x faster in sampling, with only a
small worker-time advantage. At 100x, NUTS is about1.79x faster in sampling and
also faster including worker overhead. Thus a practical rewrite removes much
of the apparent concentrated-case reliability advantage of noncentered WAL.
Selecting a parameterization after seeing results is exploratory, not an
independent validation of a selection rule. Neither sampler wins universally.

## Verification and scope

- Latest extension SHA256 and compiler/build settings: latest01/BUILD-MANIFEST.json.
  Installed/new defaults match; paths, hashes and dependency versions are in
  latest01/RUNTIME-AUDIT.json. Same version label0.3.0 does not identify a binary.
- Model value/gradient/coordinate checks passed. Two targeted adapter tests
  passed; one optional Numba test was skipped because Numba was unavailable.
  The actual native callback path was exercised by all retained sampling fits.
- 688 main and158 hybrid archive files were SHA256-verified locally. Raw arrays,
  both native binaries, model binary/source and source archive are preserved
  locally and excluded from Git. Text evidence preserves original bytes.
- All132 raw-draw summaries were independently recomputed. All36 old/new
  noncentered trajectory pairs were bit-identical. See *-RAW-AUDIT.json.
- Build attempts with missing offline dependency, missing rustc PATH and missing
  pytest are retained. The successful release build took257s, excluded from
  sampling timings. Build/test dependencies were isolated in RAM, with existing
  Python environments unchanged. No deployment or publication occurred.
- Four seeds and three related synthetic datasets do not establish real-world
  performance or a statistically precise reliability rate. The joint model has
  only14 parameters and admits cheap conditional numerical integration. These
  results do not establish decision value, profitability or unique necessity.

The evidence supports modest, geometry-dependent benefits. It does not support
a 10x claim or the assumption that conservative NUTS must be much slower.
