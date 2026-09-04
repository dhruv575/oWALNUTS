# WP36 ledger entry — chain rescue v2

Date: 2026-09-04
Status: **complete**
Decision: **no_rescue**

WP36 completed all 288 planned one-shot launches. There were 281
process-valid cells and seven process faults: six Windows heap-corruption
exits (`0xC0000374`) and one 7200-second post-result `drop/before` timeout.
Six paired triplets were invalid.

The `two_hit` candidate reduced nuisance unique-chain actions from 35 to 14,
but the exact sign test had only nine complete blocks (8–1,
`p=0.01953125`) and therefore failed its registered minimum sample size.
Failure-class efficacy was 1–0 with nine ties (`p=0.5`). Paired
posteriordb raw-to-credited passes were `observe` 71→71, `current` 74→71,
and `two_hit` 76→72.

`current` recorded 117 restart events, five mapped origin overwrites, and two
unknown-origin actions. `two_hit` recorded 58, five, and two. The frozen
stable-origin classifier found only pathological/frozen ARMA and
lotka_volterra starts and zero HMM origins, limiting substantive
interpretation without changing the fallback.

The `two_hit` funnel full gate passed 4/12 seeds; signed tail-z failures were
92107, 92111, and 92112, with the registered gross red line at 92111.
No-fire passed. The available-case efficiency geometric mean was
0.8931682041554473 over 77 ratios; the full registered efficiency gate
failed due to missing HMM/92104 efficiency and sub-0.90 ARMA/HMM model
medians.

Independent prediction outcomes were P1 false, P2 false, P3 false, P4 false,
P5 false, P6 true, P7 false, and P8 true. The frozen mechanical decision is
`no_rescue`.

The uncorrected as-executed analysis is preserved in commit `b8aee0f`.
`POST-RUN-CORRECTION.md` documents reporting-only corrections. No evidence
cell was rerun.
