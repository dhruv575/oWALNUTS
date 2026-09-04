# sblrc process stability diagnostic v1 — results

A process-stability fault reproduced in 1/46 diagnostic children: sample-r4-t4-990603 exited 0xC0000374 (STATUS_HEAP_CORRUPTION), silently, after the last durable heartbeat drop/before. The uninstrumented interval spans target drop plus the attempted next heartbeat; it is consistent with teardown but does not prove that teardown caused the fault.

These are process-lifecycle diagnostics, not posterior-performance evidence. Durations are reported only to identify hangs/timeouts.

| matrix row | config | planned | success | faults | silent | raw missing | heartbeat incomplete | duration median / max (s) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| load-r1-t1 | r1 / t1 / c0 | 12 | 12 | 0 | 0 | 0 | 0 | 0.0459 / 0.3731 |
| load-r4-t4 | r4 / t4 / c0 | 12 | 12 | 0 | 0 | 0 | 0 | 0.5246 / 0.6735 |
| eval-r1-t1 | r1 / t1 / c0 | 6 | 6 | 0 | 0 | 0 | 0 | 0.0633 / 0.0693 |
| eval-r4-t4 | r4 / t4 / c0 | 6 | 6 | 0 | 0 | 0 | 0 | 0.6039 / 0.6816 |
| sample-r1-t1 | r1 / t1 / c1 | 3 | 3 | 0 | 0 | 0 | 0 | 0.1921 / 0.2190 |
| sample-r4-t4 | r4 / t4 / c4 | 3 | 2 | 1 | 1 | 0 | 1 | 0.7983 / 3.3127 |
| repeat-load-r1-t1 | r1 / t1 / c0 | 2 | 2 | 0 | 0 | 0 | 0 | 0.3789 / 0.3910 |
| repeat-load-r4-t4 | r4 / t4 / c0 | 2 | 2 | 0 | 0 | 0 | 0 | 10.4531 / 11.2108 |

## Classification

- Matrix complete: `True` (46/46 records).
- Faults: `1`; silent faults: `1`.
- Evidence seed 90101 run: `False`.
- Root cause: `not established`.

## Fault records

- `sample-r4-t4-990603`: child return code was 3221226356, not zero, required heartbeat sequence is incomplete; return `0xC0000374`; last heartbeat `drop/before`. The following interval includes target drop and the attempted next heartbeat; this is consistent with teardown, not proof of causation.
