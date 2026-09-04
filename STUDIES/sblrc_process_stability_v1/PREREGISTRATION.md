# sblrc silent-process stability diagnostic v1 — preregistration

Frozen 2026-09-04 before implementation was executed or any diagnostic child
was launched. The machine-readable protocol is `protocol.json`. The source
tree under test is WP35 commit `8a8f8211cb87330e7c61fe3a4596aa32cd404d12`.

## Scope and question

WP35 recorded one `sblrc` oWALNUTS child, evidence seed 90101, ending nonzero
without stderr or a raw result. This separate diagnostic asks only whether a
silent process failure reproduces while loading, evaluating, sampling, or
dropping the same already-compiled BridgeStan model.

This is process-stability instrumentation, not posterior-performance evidence.
It does not rerun or reinterpret the WP35 evidence cell, compare posterior
quality, tune the sampler, or decide a default. Seed 90101 is forbidden.

## Fixed external inputs

The diagnostic reads, but does not copy or modify:

- `C:\dev\owalnuts-wt\posteriordb-v6\STUDIES\posteriordb_bench_v6\models\sblrc__blr_model.so`
  (3,891,206 bytes; SHA-256
  `b77acc367c40b3afbb51f239e87fe896c1e7631643352361734b0dbacb0c50f1`);
- the adjacent `sblrc__blr.data.json` (11,288 bytes; SHA-256
  `2227de01d39e50560dd8341a84ed176a2a081cc8c8a841261dd4d6c38b47dc9c`).

The already-existing Python 3.11 environment beside the WP35 study may run
the orchestrator. The Rust diagnostic crate is built in this new study.

## Fixed matrix

Each row runs in a fresh child process unless explicitly named in-process:

| mode | replicas / threads / chains | repetitions | work |
|---|---|---:|---|
| `load_drop` | 1 / 1 / 0 | 12 | one load and explicit drop |
| `load_drop` | 4 / 4 / 0 | 12 | four independent library replicas and explicit drop |
| `evaluate` | 1 / 1 / 0 | 6 | uniform initialization, then 256 fused evaluations |
| `evaluate` | 4 / 4 / 0 | 6 | four starts, then 256 fused evaluations per worker |
| `sample` | 1 / 1 / 1 | 3 | exactly 1,000 warmup + 1,000 retained transitions |
| `sample` | 4 / 4 / 4 | 3 | exactly 1,000 warmup + 1,000 retained per chain |
| `repeat_load_drop` | 1 / 1 / 0 | 2 | 20 load/drop cycles in one process |
| `repeat_load_drop` | 4 / 4 / 0 | 2 | 20 four-replica load/drop cycles in one process |

The fixed diagnostic seed ranges are 990101–990112, 990201–990212,
990301–990306, 990401–990406, 990501–990503, 990601–990603, 990701–990702,
and 990801–990802, assigned to the rows above in order. An exact whole-number
search over tracked source and non-artifact study files found none before
freezing. They are explicitly diagnostic identifiers and cannot be used as
posterior evidence.

## Instrumentation and classification

The Rust child atomically publishes immutable heartbeat event files before and
after model load, initialization, mode work (evaluation or sampling), raw
result writes, and explicit target drop where execution reaches those stages.
In-process repetition includes cycle numbers on load and drop events. A temp
file is flushed and renamed to a previously absent final event name in the
same directory.

The Python parent records elapsed wall time, timeout state, raw-output
existence, stdout and stderr, and the Windows process return code represented
as Python raw, signed 32-bit, unsigned 32-bit, and eight-digit hexadecimal.
It preserves every child record; failures are not rerun.

A child is a silent failure when it does not complete successfully and both
captured stdout and stderr are empty. A fault reproduces if any child times
out, exits unsuccessfully, lacks its final raw result, reports an internal
error, or fails the required heartbeat sequence. Silent reproduction is
reported separately from non-silent faults. The last durable heartbeat
localizes a failure stage but does not establish a root cause.

## Rules

- Run the fixed order above and report every planned child.
- Do not run seed 90101.
- Do not use posterior accuracy, ESS, R-hat, gradients per second, or timing
  comparisons as evidence; durations are process diagnostics only.
- Do not modify `STUDIES/posteriordb_bench_v6`, its artifacts, or the external
  model environment.
- Do not tune, substitute inputs, or rerun a failed child after observing it.
- If the fault does not reproduce, say so and do not invent a cause.
