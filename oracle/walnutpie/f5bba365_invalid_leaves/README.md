# Walnutpie zero-density (failed-evaluation) macro-leaf differential oracle

`invalid_leaf_cases.json` contains 4,000 macro-leaf decisions produced by the
**unmodified** upstream `walnutpie::detail::macro_step` (commit
`f5bba36529697c34567a2944be36b68e305c546d`, headers at
`flatironinstitute/walnutpie`) on Neal's 10-D funnel
(`omega ~ N(0, 9)`, `x_i | omega ~ N(0, exp(omega))`) with a hard wall, using
the upstream `walnutpie::detail::NoExceptLogpGrad` wrapper
(`walnutpie/util.hpp`), which maps a throwing target evaluation to
`logp = -inf`, `grad = 0`.

Two wall geometries alternate by case index:

| wall | region that throws | start positions |
|---|---|---|
| `neck_omega` | `omega < -7` | `omega` uniform on `[-7, -3]`, `x` from the conditional |
| `body_x1` | `x_1 > 0.8` | `omega` uniform on `[-2, 2]`, `x` rejection-sampled outside the wall |

Tuning families cycle as in the funnel oracle (`0.36/10/1/0.21`,
`0.36/8/2/0.5`, `0.6/6/1/1.0`, `0.36/5/4/0.21`). Every start is valid; momenta
are standard normal; direction is a fair coin.

Generator: `generate_invalid_leaves.cpp` (this directory). It links only the
upstream headers plus Eigen and records, per case: inputs, wall, direction,
whether the leaf was accepted, total fused target calls (forward attempts plus
reverse checks), the number of calls that threw (`zero_density_evaluations`),
the level-0 adaptation statistic, and the accepted endpoint. Regenerate with

```console
g++ -std=c++20 -O2 -I<walnutpie>/include -I<eigen> generate_invalid_leaves.cpp -o gen
./gen 4000 20260831 > invalid_leaf_cases.json
```

Of the 4,000 leaves, 3,080 are accepted, 343 call the target inside the wall at
least once, and 50 of those are accepted after refining away from the wall.

The Rust test `oracle_tests::invalid_leaf` replays every case through
`kernel::macro_leaf_observed` with a target that returns `(-inf, 0)` inside the
wall and requires the acceptance decision, target-call count, zero-density call
count, adaptation statistic, and endpoint to agree to `1e-11`, and that no
zero-density point is classified as an invalid evaluation. Before the `v10`
zero-density correction, every leaf that touched the wall stopped as an
invalid evaluation on its first wall call.

Upstream code is MIT licensed; see the repository `NOTICE` and
`THIRD_PARTY.md`.
