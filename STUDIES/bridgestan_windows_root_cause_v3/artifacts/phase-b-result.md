# WP50C Phase B result: stress gate

The preregistration is commit 6c166c2a. There was one launch with 480/480
children recorded, no missing records, no timeouts and no manipulation
failures. At `load/after` every child had exactly the runtime modules expected
for its arm.

## Counts (event-inclusive, after the correlation correction below)

- **`static_long`** (static DLLs, 1000/1000): **0/300** faults, 95% upper
  bound 0.99%. Median contended wall time 2.33 s.
- **`control_long`** (old dynamic DLLs, 1000/1000): **1/60**, from
  `control_long-50700406`:
  - rc 0xC0000374; Event 1000 in ntdll.dll, c0000374, offset 0x118095;
  - last heartbeat `sampling/before`, so it died *during* sampling, not at
    teardown.
- **`static_short`** (static, 4/4): **0/60**, upper bound 4.9%.
- **`control_short`** (dynamic, 4/4): **1/60**, from `control_short-50700620`:
  - rc 0xC0000374; ntdll c0000374;
  - last heartbeat `process/complete`, i.e. at exit.

**Gate verdict (as corrected): `fix_supported`.** The static arm had 0/300 and
the control reproduced.

**Strength.** The evidence is weaker than the power calculation assumed. The
control rate came out at 1/60 (1.7%), not the 5% assumed.

- Secondary one-sided Fisher test, `control_long` 1/60 vs `static_long`
  0/300: p = 0.167.
- Pooling both shapes, dynamic 2/120 vs static 0/360: p = 0.062.
- If the static DLLs faulted at the pooled dynamic rate of 1.67%,
  P(0/360) = 0.0024.

## Analysis correction (disclosed; records unchanged)

The analysis as preregistered reported `fix_not_supported` with
`static_long` 1/300. That was a false attribution.

- **What happened.** All four arms share one exe path, and Windows reused PID
  26612. Event record 30065 (01:56:27Z) belongs to `control_short-50700620`:
  that child was launched at 01:56:24Z, returned 0xC0000374 and lasted 45 s.
  PID + path matching also gave the same event to `static_long-50700229`,
  which launched 15 minutes later (02:11:45Z), exited 0 and passed every
  heartbeat.
- **The fix.** One event cannot belong to two processes. The correlation now
  also requires the event time to fall inside the child's launch window,
  from 1 s before launch to 5 s after return. A unit test covers the case.
- **What was preserved.** The literal as-preregistered summary is
  `phase-b/summary-as-preregistered-pid-only-correlation.json`.
- **Side effect.** The run's only two Event 1000 rows now map one-to-one onto
  the two nonzero-rc control faults.
- **WP50B is unaffected.** It used per-cell exe directories. A cross-check
  found one PID reuse there (event 30058), and it was correctly not matched to
  the Git-directory child.

## Observations

- The dynamic fault occurred once mid-sampling. The concurrent-replica path
  with the WinLibs runtime can corrupt the heap while running, not only at
  process teardown. Both faults are `STATUS_HEAP_CORRUPTION` reported from
  ntdll, the same signature as `bridgestan_owned_worker_v1`.
- The arm "60 static children without owned-worker serialisation" ran as
  `static_short`, which shares the gate's code path (9edcbac has no owned
  worker): 0/60. Every `static_long` child was also unserialised
  multi-replica, giving 0/360 static unserialised children in total.

Phase C proceeds, conditional on the corrected verdict. This dependence is
stated in the Phase C preregistration.
