# Continuation prototype (correctness checks and development benchmarks)

This additive CFunc-only prototype avoids repeating adaptation when collecting
additional retained draws. It does not change posterior geometry, numerical
kernel behavior, ordinary `sample`, or sampler defaults. Focused replay and
lifecycle checks pass on the pinned Rust 1.88 GNU toolchain. Development
benchmarks now measure complete workflows; broad reliability and interval
calibration remain unestablished.

In the audited dense-flow comparison, the T128 workflow took 17.023 seconds
with continuation versus 21.235 with full restarts, both first passing at 2,000
draws per chain. Every shared retained array matched exactly. At T1000,
continuation reduced consumed time from 904.697 to 400.939 seconds, but both
procedures failed endpoint precision at the 8,000-draw cap; this is not a
time-to-success improvement. An earlier local-model fit was slower overall with
continuation because output overhead outweighed saved sampling work. These
results support measuring full invocation costs, not promising automatic speedups.
See [the study findings](../../STUDIES/options_flow_v1/PILOT_FINDINGS.md) for
reference comparisons, failed cases, real-data computations and limitations.

```python
with owalnuts.start_session(target, init=starts, chains=4,
                           warmup=1000, max_draws=8000, seed=123) as session:
    warmup = session.adapt()
    chunks = [session.draw(1000), session.draw(1000)]
    draws = np.concatenate([chunk.samples for chunk in chunks], axis=1)
```

Only explicit finite `(chains, dim)` starts and `CFuncTarget` targets are
accepted. Sampling is sequential and supports identity/diagonal mass; dense,
structured, parallel and rescue modes are rejected. The worker owns the whole
target, including compiled callback keepalive, until the final callback ends.

`max_draws` is the lifetime retained limit per chain. Admission and the target
evaluation budget cover the entire session across every chain. Warmup occurs
once. Each returned chunk contains only new samples and corresponding transition
diagnostics, while work summaries, metric and tuning are explicitly cumulative.
The authoritative `cumulative_target_calls` counts actual started callbacks,
including initial-step searches; it is not a sum of potentially shared search
attributions in per-chain telemetry.

Construction/admission makes no log-density/gradient callbacks (dimension
queries are allowed). The first `adapt().target_calls` includes initialization
and shared initial-step-search work. `initialization_target_calls` reports that
subset, not an additional charge. Summing warmup and all retained chunk
`target_calls` must equal an external callback counter started before public
construction. Existing ordinary-run telemetry totals can omit separate
adaptation search events; compare actual callbacks or identically scoped
counters rather than equating differently scoped labels.

This prototype reserves capacity for the full maximum draw budget and retains
all history inside each `ChainRun`, then copies newly requested chunks for the
caller. It is bounded by the declared budget but is **not constant-memory
streaming**. Large `max_draws * chains * dimension` can require substantial
memory even if the caller stops early. Reclaiming old internal samples or
incremental allocation is a separate change that must preserve replay tests.

Invalid requests rejected before advancement do not change the chain. Any
execution error, panic or cancellation during advancement terminates the
session; previously returned chunks remain available and no partial failing
chunk is returned. `progress()` preserves failure text, actual target-call count
and completed transition indices for diagnosis. No automatic retry or rollback.
It is a **completed-request/error snapshot**, not a live progress feed: during
an active warmup or retained request its counters can remain zero or reflect
the previous request. Callers should mark and time adapt/draw entry and return
when displaying the active phase. This prototype adds no per-transition Python
callbacks or live polling overhead to the sampler.

Concurrent mutating calls fail immediately. `cancel()` signals cooperative
cancellation; `close()` signals cancellation and joins with the interpreter
detached. Close is idempotent. Dropping without close signals cancellation but
does not block a Python destructor. An arbitrary native callback that never
returns cannot be safely preempted in-process; use process containment for a
hard timeout. The worker retains its target even after the handle is dropped.
At the generic Rust boundary, calling close from the session's own callback
signals cancellation and returns a configuration error before acquiring the
join lock. It never joins itself; an external caller can still close and reap
the worker. Ordinary CFunc callbacks remain subject to their native ABI and
reentrancy contract.

Exact replay tests compare uneven chunks to uninterrupted sampling using the
same maximum retained budget, seeds, build and inputs. Shared chain-zero initial
step search, cache settings, adaptation boundaries and every cumulative counter
are part of this contract. No RNG state is serialized or reconstructed between
chunks, and no unsafe self-referential structure is used.

## Validation performed in the isolated worktree

* `cargo +1.88.0-x86_64-pc-windows-gnu test --locked --features research --test continuation_session --test sampler_api`: 7 continuation and 17 facade tests passed.
* `cargo +1.88.0-x86_64-pc-windows-gnu test --locked --test kernel_fingerprint`: both bit-exact kernel fingerprints passed.
* Python debug extension built with `cargo +1.88.0-x86_64-pc-windows-gnu build --locked --manifest-path integrations/python/Cargo.toml`, with `PYO3_PYTHON` pointing to the existing workflow interpreter. The DLL was copied only into the isolated source package; no main environment package was installed or replaced.
* With `PYTHONPATH` set to that isolated package, `pytest integrations/python/tests/test_continuation_session.py -q`: 4 passed, covering both cache settings, all nine ordinary diagnostic arrays, callback-code lifetime and cancellation.
* Two existing CFunc adapter regressions (parallel Gaussian and zero-density wall) passed against that isolated extension.

The first conservative-admission test fixture incorrectly requested zero
warmup with adaptation enabled; it was corrected to explicit no-adaptation and
identity metric, preserving existing configuration validation rather than
changing it. All results above concern the corrected fixture.
