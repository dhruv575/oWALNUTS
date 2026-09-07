# Methods: how a study is run here

These rules were followed for every evidence study from WP2 onward and are
the reason the ledger can be trusted. They are stated once here; the
programme documents restate the older versions.

## Preregistration

- `PREREGISTRATION.md` and `protocol.json` are written and committed before
  the first evidence cell. They fix the target set, arms, seeds, gates,
  statistic, decision rule and predictions. Amendments are dated files
  (`AMENDMENT-N.md`) written before the affected cell is interpreted.
- The decision rule is mechanical. Several studies were decided against the
  hypothesis that motivated them (WP26, WP27's default, WP29's regularisation
  arm, WP34, WP36's candidate, WP37A, WP39, WP39B). One default change was
  post hoc (WP31 to WP32) and is labelled as such everywhere it is cited.
- Instrumentation and diagnostic studies (WP27's diagnosis, WP30, WP40,
  `sspd_target_fatal_diag_v1`) are not preregistered and cannot decide a
  default. They use exploratory seeds that a later decision study may not
  reuse.

## Seeds

- Every evidence seed is grep-verified unused in the repository before the
  freeze (exact word, excluding numeric substrings of floats). Diagnostic
  seeds live in a separate high range (99xxxx).
- A killed or crashed cell is recorded as a result. A cell is rerun only when
  the driver was killed mid-cell by the host, and the rerun is recorded as a
  deviation. Cells are never replaced after a result exists.
- Paired designs share starts across arms per seed.

## Statistics and gates

- The posteriordb protocol (v3 onward): 17 posteriors at posteriordb
  `28f8d3d` with reference draws, 4 chains, 1,000 warmup and 1,000 retained,
  every sampler at its defaults; gates rank R-hat at most 1.01 and bulk and
  tail ESS at least 400 on every reference parameter with zero retained
  divergences (ArviZ 0.23.4); agreement z against the reference mean with
  both MCSEs.
- The efficiency statistic is minimum bulk ESS per target call, warmup
  included, seed medians, geometric mean over models. It is the
  machine-independent figure; walls were measured on a shared machine and
  are upper bounds.
- Funnel side checks report the exact tail-mass z from the MCSE of the
  indicator, per seed, and require |z| at most 2 on every seed.
- Decision rules usually pair a geomean threshold (1.10 or 1.15x) with a
  no-model-below clause (0.85 or 0.90x), a gate count, and side checks.

## Bit-identity as the safety rail

- `tests/kernel_fingerprint.rs` pins the frozen `walnutpie` defaults;
  `ALGORITHM_REVISION` did not change during the 0.2 programme.
- Every refactoring or performance change had to reproduce the fingerprints
  (WP30's cache, WP33's driver refactor). Optimisations that would have
  changed floating-point operation order were rejected.
- Every research-only option is tested bit-identical when off.
- Kernel semantics are checked against differential oracles generated from
  the unmodified upstream `walnutpie` headers (4,000-leaf fixtures for funnel
  leaves and invalid leaves, agreement to 1e-11).

## Artifacts

- Each study directory carries `README.md`, `LEDGER-ENTRY.md`, the protocol,
  the harness source, `checksums.py` and `CHECKSUMS.sha256` over every
  committed file and the hashes of uncommitted raw draws.
- The ledger entry is appended, never edited, and follows the template:
  ordered time, protocol and config, seeds, status, outcome, diagnostics,
  artifacts, conclusion (supported and not supported), next decision.
- Large raw trees (for example WP37B's 119 GB) stay on the study machine
  with a size-and-hash manifest committed.

## Environment notes that cost time

- Toolchain `RUSTUP_TOOLCHAIN=1.88.0-x86_64-pc-windows-gnu`; CI runs clippy
  with `-D warnings` on every target and feature. No MSVC tools locally;
  Linux and MSVC are verified through GitHub Actions.
- BridgeStan must be built without `STAN_THREADS` on mingw-w64 (10x per-call
  cost otherwise); use one loaded module per thread.
- Windows native lifetime faults (`0xC0000374`) in the replicated BridgeStan
  path are mitigated only by the owned-one-worker backend; keep the raw
  diagnostic trees immutable.
- Long runs are launched detached and watched through a done marker; the
  host kills foreground and background waiters under memory pressure.
- Profiler cells use four threads; run them four wide on the 16-core machine
  (`STUDIES/warmup_gap_diag_v1/run_parallel.py`) and screen on the four
  deciding targets plus five fast controls before any 17-model sweep. A
  three-arm, two-seed screen takes about 20 minutes; a serial 17-model sweep
  of four arms took about five hours.
- Telemetry checkpoints are zero-indexed.
