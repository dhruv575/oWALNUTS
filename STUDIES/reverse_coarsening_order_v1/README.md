# reverse_coarsening_order_v1 (WP37B)

Status: **preregistered scaffold only — frozen before implementation, build, or
evidence**.

Controlling review clarification: [`AMENDMENT-1.md`](AMENDMENT-1.md). It
replaces the original pass label and action: a pass can qualify only explicit
Rust opt-ins for deterministic finite-or-recoverable targets. No generic,
walnutpie, high-level sampler, or Python default may change.

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
Every default remains `FinestToCoarsest`; Python is unchanged. This scaffold
itself authorizes and contains no code or default change.
