# Walnutpie funnel macro-leaf differential oracle

`funnel_leaf_cases.json` contains 4,000 macro-leaf decisions produced by the
**unmodified** upstream `walnutpie::detail::macro_step` (commit
`f5bba36529697c34567a2944be36b68e305c546d`, headers at
`flatironinstitute/walnutpie`) on Neal's 10-D funnel
(`omega ~ N(0, 9)`, `x_i | omega ~ N(0, exp(omega))`), identity mass.

Generator: `generate_funnel_leaves.cpp` (this directory). It links only the
upstream headers plus Eigen and records, per case: inputs (position, momentum,
macro step, halvings, minimum micro steps, tolerance), direction, whether the
leaf was accepted, the number of fused target calls consumed (forward attempts
plus reverse checks), the level-0 adaptation statistic passed to the step-size
handler, and the accepted endpoint (position, momentum, gradient, log density,
joint log density).

Cases cycle through four tuning families:

| family | macro step | halvings | min micro | max error |
|---|---:|---:|---:|---:|
| 0 | 0.36 | 10 | 1 | 0.21 |
| 1 | 0.36 | 8 | 2 | 0.5 |
| 2 | 0.6 | 6 | 1 | 1.0 |
| 3 | 0.36 | 5 | 4 | 0.21 |

Starting `omega` is uniform on `[-8, 4]` so leaves span the neck and the
mouth. Regenerate with

```console
g++ -std=c++20 -O2 -I<walnutpie>/include -I<eigen> generate_funnel_leaves.cpp -o gen
./gen 4000 20260831 > funnel_leaf_cases.json
```

The Rust test `oracle_tests::funnel_leaf` replays every case through
`kernel::macro_leaf` and requires the acceptance decision, target-call count,
adaptation statistic, and endpoint to agree to `1e-11`. Before the `v9`
endpoint-criterion correction, 1,555 of the 4,000 cases disagreed.

Upstream code is MIT licensed; see the repository `NOTICE` and
`THIRD_PARTY.md`.
