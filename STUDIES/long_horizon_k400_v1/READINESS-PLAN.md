# Literal readiness plan (unexecuted)

One new 600-second Linux envelope (plus up to five seconds bounded cleanup), aggregate sampled 4 GiB RSS and 1 GiB output. All source/runtime identities are checked before and after; output scans are every two seconds and may overshoot between samples. Ownership/RSS/deadline checks remain frequent.

Run all deterministic fixtures, including the two POSIX monitor fixtures. Then run four concurrent four-update N250/K400 lanes on cores 0–3, 4–7, 8–11, 12–15. Each uses the literal return formula in readiness.py, the already-used development initial/warm seeds 99371041/99371042, and full six-query plus analytic-scale scoring at ticks 1 and 4. Identical development seeds across these lanes are intentional and are not study replication.

After their owned groups drain, run one independent reference on cores 0–3 using the same literal data, sample seed 99371042 and model seed 99371043, full four chains × 4000 retained draws after 2000 warmup, unchanged production extraction/scoring/precision code. These are development-only namespaces previously audited apart from production reservations. No generator call, study data or reserved study RNG is allowed. No retries or parameter/cap changes within this attempt.

The binder emits a pending manifest. A separate exact status-only copy `literal_readiness_authorized` admits only readiness.py; production worker and campaign reject it. Production still requires separately reviewed `frozen_authorized` bytes after readiness succeeds. Preserve and hash exact manifest, bundle, logs, native/score arrays, compiler snapshots, all monitor outputs and source/runtime postchecks. A successful literal run validates integration and measures overhead, not broad-prior feasibility or MCMC qualification.
