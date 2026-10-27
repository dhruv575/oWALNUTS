# Fresh risk confirmation: operational proposal

Status: draft, no acquisition, data generation, RNG use or execution authorized by this file. Parent owns AWS lifecycle; keep the instance running between reviewed experiments. No host shutdown belongs in this workflow.

The scientific owner fixes December 2025 (1,488 origins), January 2026 (1,488), and February 2026 (1,344): 4,320 origins and 24 independent posterior-reference fits. Acquisition is the contiguous 96-day November 25 through February 28 interval, 4,608 bars, with no replacement months. Native inference remains the verified E64 fixed-window K400 implementation. Tail arithmetic remains the verified E65 P5/P95 implementation. This proposal changes scheduling and calendar adapters, not algorithms.

Proposed fixed job queue (57 jobs):

1. Three native candidate jobs on cores 0-3, 4-7, and 8-11, one continuous stateful lane per month.
2. Three independent baseline jobs, serialized after native drain.
3. Twenty-four independent reference fits, canonical month/index order distributed by global index modulo four. Each queue runs six fits sequentially on its own four-core set, including 12-15. Keep each fit as the existing isolated subprocess and compiler workspace; do not add a private compiled-model cache or alter chain seeds.
4. Twelve stateless candidate-tail shards, canonical month-major tick index modulo twelve, 360 origins each, one core per shard.
5. Twelve reference-tail shards, two references each, only after all candidate-tail groups drain, preserving candidate/reference MCSE comparison.
6. Three final monthly risk reports, then metadata-only aggregate and terminal accounting. No redundant original density-report bootstrap is required.

Every phase waits for all previous groups to drain. A scientific unavailable result remains in the planned denominator. Unsafe cleanup or resource failures block later launches and preserve every not-started slot. Native, baseline, reference and tail availability remain distinct. The terminal ledger retains all 4,320 origins and 24 reference slots even if no reports finish.

Proposed fixed bounds pending literal readiness: 3,600 seconds internal and 3,720 external; native phase 1,800; baselines 120; independent references 600 with 180 seconds per fit; candidate tails 600; reference tails 180; reports 120. These phase maxima total 3,420 seconds, leaving 180 seconds for admission and terminal work. Aggregate RSS 12 GiB; reference fit RSS 3 GiB; tail worker RSS 1 GiB; total new output 2 GiB. Output is sampled every two seconds plus a final post-drain scan, not a hard filesystem quota. Owned CPU/RSS/affinity samples every five seconds will report denominators appropriate to each phase (12 candidate cores, 16 reference cores, 12 tail cores), with orchestration overhead explicitly included.

Cost basis (metadata only, no new outcome calculations): E64 native month jobs took 726.3 to 794.6 seconds; its 24 reference jobs took 21.49 to 22.18 seconds each (523.4 seconds serialized), with largest reference group RSS 2,026,393,600 bytes. E65 candidate-tail workers took about 210.3 to 210.8 seconds and reference-tail workers 16.0 to 16.4 seconds. Four-way reference concurrency suggests about 130 seconds before contention, so roughly 20 minutes is a planning estimate, not a guarantee. New compact arrays are about 234 MB plus diagnostic, compiler, metadata and cache outputs; prior complete native evidence used about 701 MB and tail outputs 57 MB. Two GiB is conservative for retained artifacts but must include all new compiler/JIT caches.

Readiness must exercise four simultaneous full-size reference paths with literal data, unchanged engine options, separate compiler directories, fresh contained caches, and the same group monitor. Aggregate memory/CPU pressure and each worker's native/extraction/scoring path must pass before production. Prior twelve-way tail readiness already established the arithmetic path; a new calendar adapter needs deterministic boundary fixtures, not market outcome tuning. No study seeds or acquired returns enter readiness.

Seed namespaces will be reserved by pure integer enumeration against E61-E65 and known development inventories, followed by a bounded exact-token project-source/metadata search. No broad raw-array search and no claim of universal RNG collision proof. Proposed new namespaces are based on 20261029 for native/bootstraps and 602710000 for independent reference model/sample seeds, subject to the actual collision audit before freeze.
