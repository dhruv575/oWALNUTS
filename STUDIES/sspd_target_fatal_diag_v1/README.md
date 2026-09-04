# sspd_target_fatal_diag_v1 — why the WP37B state-space cell died

**Diagnostic only.** No evidence seed was used (seeds 996101–996113), no
study cell was rerun, and nothing here is posterior-performance evidence.
The question is narrow: is the fatal target error that stopped WP37B
(`STUDIES/reverse_coarsening_order_v1`, cell 72, chain 1, transition 1)
caused by the reverse-check order under test, by the frozen
polyscope-canonical-v2 target, or by the kernel?

## Setup

`src/main.rs` includes the frozen target source from
`sspd11_confirmation_v1/primary/src/canonical.rs` by path, reads the WP37B
fixture and the sspd-11 starts, and runs `owalnuts::sampler::Sampler` with the
WP37B cell configuration except for length (4 chains, warmup 60, draws 20,
max depth 10, eight refinement levels, `max_error = 1`, divergence threshold
1000, diagonal metric, default adaptation, worst-case admission). The
`ReverseCoarseningOrder` research option is not set, so only the incumbent
finest-to-coarsest order runs. Two arms:

- `none`: the target exactly as frozen. Its `recoverable()` classifier maps
  `exp` overflow to `TargetError::recoverable` and everything else, including
  the final "canonical log density or gradient is not representable as finite
  f64" check and "observation variance at index 0 is not positive and
  finite", to a fatal `TargetError::new`.
- `repair`: identical, except every fatal-classified target result is
  reclassified as recoverable before it reaches the kernel.

Two initial step sizes: 0.5 (frozen by WP37B) and 0.1 (used by the sspd11
studies that sampled this target without incident).

```
RUSTUP_TOOLCHAIN=1.88.0-x86_64-pc-windows-gnu cargo build --release
./target/release/sspd-target-fatal-diag-v1 <seed> <none|repair> <warmup> <draws> [initial_step]
```

`results.txt` is the complete 52-run battery (13 seeds x 2 arms x 2 steps).

## Result

| initial step | arm    | runs completed | failure kind                                       |
|-------------:|--------|---------------:|----------------------------------------------------|
| 0.5          | none   | 0 / 13         | 12 fatal target error, 1 kernel nonfinite position |
| 0.5          | repair | 11 / 13        | 2 kernel nonfinite position                        |
| 0.1          | none   | 11 / 13        | 2 fatal target error                               |
| 0.1          | repair | 13 / 13        | none                                               |

Every failure is at transition 0, 1 or 2 of a chain (14 of 17 at transition
1), i.e. during the first orbits at the initial step, before any adaptation.
The fatal target messages were "canonical log density or gradient is not
representable as finite f64" (10) and "observation variance at index 0 is not
positive and finite" (4). At step 0.5 the target rejects a large share of the
first transition's evaluations as recoverable overflow (7.6k to 855k per
completed run against 0.15M to 1.7M total calls); at step 0.1 the counts are
36 to 249.

## Reading

1. **The WP37B failure is a target defect, not an order effect.** The frozen
   target's classifier treats two reachable non-finite outcomes as fatal
   while treating the `exp` overflows that precede them as recoverable. Any
   large enough trial step reaches them; at the WP37B initial step it happens
   on every diagnostic seed, and at the sspd11 step on 2 of 13. Reclassifying
   them as recoverable (a zero-density leaf, which is what Stan does for a
   thrown log density) removes every target-side failure.
2. **A second, kernel-side gap remains.** With the target repaired, 2 of 13
   seeds at step 0.5 still abort with `ErrorKind::Numerical`, "kernel
   attempted a nonfinite target position": the integrator produced a
   non-finite position and the kernel refuses to evaluate it and ends the run.
   Stan treats the same event as a divergent leaf and continues. Whether
   oWALNUTS should do likewise is a kernel robustness decision that has not
   been preregistered; it is recorded in the programme document as an open
   line and is **not** changed here.
3. **Consequence for reverse-coarsening.** A renewed WP37B protocol must
   either omit the state-space target or use a repaired copy whose classifier
   is fixed before evidence, with fresh seeds. The frozen copy under
   `sspd11_confirmation_v1` is not edited.
