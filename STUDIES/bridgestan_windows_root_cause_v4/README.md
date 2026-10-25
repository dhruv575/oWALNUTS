# WP50D: confirmatory stress gate (static-runtime DLLs, no owned worker)

This study is a process and engineering diagnostic, not posterior evidence.
It follows WP50C (`../bridgestan_windows_root_cause_v3`). Its rules were
frozen at `0ec73277` (`PREREGISTRATION.md`, `protocol.json`), including the
crash-event correlation by lifetime window, PID and arm exe path. It ran
once, with no post-hoc step.

## Design

- **Configuration.** The reproducing one: PowerShell launch with the WinLibs
  runtime on PATH, sblrc, 4 replicas / 4 chains / 4 threads, 1000/1000, the
  HEAD sampler, one child at a time.
- **`static_unserialised`, 1,000 children.** Static-runtime DLLs on the
  unserialised multi-replica target, which is what the opt-in would ship.
- **`dynamic_unserialised`, 300 children.** Old dynamic DLLs on the same
  target. This is the primary positive control.
- **`dynamic_owned`, 300 children.** Old dynamic DLLs on HEAD's owned worker.
  This is the coordinator's literal control. It was disclosed in advance as
  expected not to reproduce.
- **Interleaving.** Single-arm blocks of 10.

## Result (`artifacts/result.md`)

**Frozen verdict: `not_supported`.**

- **`static_unserialised`: 1/1,000 faults** (95% upper bound 0.47%). The fault
  was a sampler-reported numerical error with return code 1 ("kernel
  attempted a nonfinite target position", chain 2, transition 9). It was not
  a crash: there was no Event 1000 and no NTSTATUS code. No static child
  mapped a runtime DLL.
- **`dynamic_unserialised`: 4/300 faults**, all crashes:
  - 2 × `0xC0000374`;
  - 2 hidden exit-0 crashes, each a `c0000005` in WinLibs `libwinpthread-1.dll`.
- **`dynamic_owned`: 0/300.**
- **Fisher, one-sided:** primary control against static, p = 0.0114.

Crash-type faults alone were static 0/1,000 against dynamic-unserialised
4/300. That comparison is post hoc and descriptive. Whether the static error
is a seed-deterministic numerical event or a symptom of corruption needs a
separately preregistered deterministic replay of seed 50801734.

## Reproduce

```
python build_child.py && python run_gate.py verify && python run_gate.py probe
python run_gate.py analyze        # the single run already happened
python checksums.py verify
```

The static DLLs are the WP50C Phase A products, hash-pinned in
`protocol.json`.
