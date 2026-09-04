# reverse_coarsening_order_v1 (WP37B)

Status: **paused incomplete on 2026-09-04; 72 of 84 cells authenticated,
cell 72 failed, 11 cells never launched; partial record archived; verdict
`KEEP_FINEST_TO_COARSEST`; no default changed.** See
[`LEDGER-ENTRY.md`](LEDGER-ENTRY.md) for the pause record and
`evidence/ARTIFACTS-MANIFEST.sha256` for the SHA-256 and byte size of every
uncommitted telemetry file under `evidence/artifacts/` (119 GB, ignored by
Git, kept on the study machine). Nothing under `evidence/` was rerun,
replaced, or deleted.

Controlling review clarifications, in order:
[`AMENDMENT-1.md`](AMENDMENT-1.md), then
[`AMENDMENT-2.md`](AMENDMENT-2.md), then final
[`AMENDMENT-3.md`](AMENDMENT-3.md). The latest amendment controls conflicts,
freezes exact callback accounting, target configuration, and fatal locations,
and corrects the nonexistent A9 reference. No further protocol amendment is
expected. A pass can qualify only explicit Rust opt-ins for deterministic
finite-or-recoverable targets. No generic, walnutpie, high-level sampler, or
Python default may change.

`PREREGISTRATION.md` and `protocol.json` freeze a two-arm mechanical study of
reverse-level traversal at fixed `delta = 1`:

- incumbent `FinestToCoarsest`;
- research-only candidate `CoarsestToFinest`.

Both arms generate identical coarse-step/micro-step pairs with the current
repeated arithmetic. Only traversal order changes, and the first accepted or
invalid reverse attempt rejects the leaf. Existing walnutpie defaults, replay,
fingerprints, and algorithm revision v10 remain unchanged.

The evidence manifest is exactly 84 one-shot cells:

- 7 targets: WP35 `accel_gp`, `gp_pois_regr`, centered Eight Schools,
  noncentered Eight Schools; pure Neal funnel; pure 100-D Gaussian; canonical
  `sspd-11` state space at `T = 1000`;
- 6 paired fresh seeds: `96101–96106`;
- 2 arms, with arm order alternating by seed.

The full ordered cell IDs are frozen in `protocol.json`. The seed range was
verified absent as standalone whole-number tokens from every tracked file at
the source baseline, including tracked artifacts.

A pass requires all 84 cells to be complete, process-valid and authenticated;
exact semantic hashes, stop/rejection sequences, public errors, forward-call
traces, starts, RNG and adaptation identity; no health/invalid regression; and
all frozen call-efficiency gates. Wall time and posterior validity statistics
are descriptive and cannot select results.

Under the controlling amendment, passing can qualify only a later explicit
Rust opt-in on `KernelTuning` and high-level `Tuning` for eligible targets.
Every default remains `FinestToCoarsest`; Python is unchanged. `study.py`
prepares the authenticated static configuration, executes the ordered manifest
with immutable launch markers, and applies the frozen mechanical gates. No
evidence is launched until the core/harness and provenance commits are both
complete.
