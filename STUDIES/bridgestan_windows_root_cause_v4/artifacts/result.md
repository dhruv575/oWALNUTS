# WP50D result

The study was preregistered at `0ec73277` and launched once
(19:58–20:53 local). All 1,600 of 1,600 records are present. Nothing timed
out, nothing was interrupted, and nothing was rerun. There were 0 manipulation
failures: every static child had none of `libwinpthread-1`, `libgcc_s_seh-1`
or `libstdc++-6` mapped, and had the private `tbb.dll` after load and, where
it was reached, after drop.

The frozen analysis ran as written. There is no correction step: four Event
1000 rows were attributed, each by path, PID and lifetime, and 0 were
unattributed.

## Frozen verdict: `not_supported`

| arm | children | faults (event-inclusive) | of which crash (NTSTATUS / Event 1000) | one-sided 95% upper bound |
|---|---|---|---|---|
| `static_unserialised` | 1000 | **1** | 0 | 0.47% |
| `dynamic_unserialised` (primary control) | 300 | **4** | 4 | 3.0% |
| `dynamic_owned` (literal control) | 300 | 0 | 0 | 0.99% |

The rule required the static arm to be 0/1,000. It had one fault, so the
verdict is **not supported** under both control readings:

- `verdict_control_dynamic_unserialised = not_supported`
- `verdict_control_dynamic_owned = not_supported`

Fisher exact test, control against static 1/1,000:

- `dynamic_unserialised` 4/300: one-sided p = **0.0114**; two-sided p =
  0.0114.
- `dynamic_owned` 0/300: p = 1.0.

## The static fault (descriptive)

`static_unserialised-50801734` exited with return code 1 at about 1.7 s. Its
last heartbeat was `sampling/before`. There was no Event 1000 and no NTSTATUS
code. stderr read:

> error: kernel attempted a nonfinite target position (chain 2, transition 9);
> the integrator overflowed: try a smaller initial `step_size`, ...

This is a sampler-reported numerical error, not a process crash. It counts as
a fault under the frozen classification ("nonzero launcher return code,
missing raw output"), and the verdict stands.

Post hoc and descriptive only, not part of the verdict: counting crash-type
faults alone gives static 0/1,000 against dynamic-unserialised 4/300.

This study cannot tell whether the error is a deterministic property of seed
50801734 under this sampler, or a symptom of state corruption. Telling them
apart needs a separately preregistered deterministic replay of that seed: the
owned worker with the static DLLs, then the unserialised target with the
static DLLs. WP50C Phase C showed that the two dispatches give bit-identical
draws, so a replay that reproduces the error under the owned worker would show
it is unrelated to dispatch.

## Controls

**`dynamic_unserialised`: 4/300.**

- `50803027` and `50803071`: rc 0 with a complete heartbeat sequence, but an
  Event 1000 `c0000005` in WinLibs `libwinpthread-1.dll` at offset `0x8c89`
  at exit. These are hidden crashes, the WP50B signature.
- `50803048`: `0xC0000374` during sampling.
- `50803197`: `0xC0000374` at exit.

**`dynamic_owned`: 0/300.** The owned worker again suppressed the fault, in
line with `bridgestan_owned_worker_v1` (0/540).

Median contended wall times: static 1.69 s, dynamic unserialised 1.66 s,
dynamic owned 2.63 s.
