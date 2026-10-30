# Exact duplicate evaluation audit

All10 enabled/disabled cases preserve prior draws, target calls and diagnostics exactly. Two instrument unit tests pass. Zero exact duplicates or repeated-output mismatches were observed.

| Target | Step factor | Calls | Duplicates | Capacity-dropped calls |
|---|---|---|---|---|
| arK-arK | 1.0 | 35561 | 0 | 0 |
| sblrc-blr | 1.0 | 39640 | 0 | 0 |
| eight_schools-eight_schools_centered | 1.0 | 156191 | 0 | 29699 |
| garch-garch11 | 1.0 | 46525 | 0 | 0 |
| gp_pois_regr-gp_pois_regr | 1.0 | 115934 | 0 | 0 |
| arK-arK | 4.0 | 246339 | 0 | 115267 |
| sblrc-blr | 4.0 | 264386 | 0 | 133314 |
| eight_schools-eight_schools_centered | 4.0 | 458841 | 0 | 313760 |
| garch-garch11 | 4.0 | 165066 | 0 | 33977 |
| gp_pois_regr-gp_pois_regr | 4.0 | 399257 | 0 | 267892 |

Cache experiment justified by frozen rule: False.
At factor1, four targets have complete finite-call coverage. Centered eight schools and all factor4 cases overflow storage; zero observed duplicates does not bound duplication among unrecorded keys. No cache implementation is justified by this screen. No runtime improvement is claimed.

Next inspect existing per-phase forward/refinement/reverse work counters with unchanged trajectories before choosing another mechanism. Initial-evaluation reuse already exists; do not rediscover it as a new optimization.
