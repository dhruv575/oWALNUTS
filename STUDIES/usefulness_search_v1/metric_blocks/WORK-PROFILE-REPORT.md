# Kernel work profile

All10 replays preserve retained draws and target calls exactly. Actual calls reconcile with telemetry.

| Target | Factor | Calls | Reverse fraction | Forward not in built leaves | Fixed-draw accounting-only native ratio |
|---|---|---|---|---|---|
| arK-arK | 1 | 35561 | 5.045% | 5.045% | 0.891 |
| sblrc-blr | 1 | 39640 | 6.420% | 6.423% | 0.747 |
| eight_schools-eight_schools_centered | 1 | 156191 | 18.429% | 20.385% | unqualified/not evaluated |
| garch-garch11 | 1 | 46525 | 5.997% | 6.003% | 0.928 |
| gp_pois_regr-gp_pois_regr | 1 | 115934 | 10.260% | 10.431% | unqualified/not evaluated |
| arK-arK | 4 | 246339 | 29.227% | 30.226% | unqualified/not evaluated |
| sblrc-blr | 4 | 264386 | 29.454% | 30.368% | unqualified/not evaluated |
| eight_schools-eight_schools_centered | 4 | 458841 | 28.686% | 33.649% | unqualified/not evaluated |
| garch-garch11 | 4 | 165066 | 28.503% | 30.980% | unqualified/not evaluated |
| gp_pois_regr-gp_pois_regr | 4 | 399257 | 29.285% | 31.136% | unqualified/not evaluated |

The last column is arithmetic only: hold the observed draws fixed and remove all reverse calls and forward calls not attached to built leaves. It is not an attainable speedup, not a bound on a different algorithm, and not permission to remove correctness checks. On the three qualified factor1 targets it still falls below native NUTS. Improving those results requires changing mixing behavior as well as, or instead of, this accounting overhead.

Factor4 spends roughly60% of calls outside built-leaf forward work, consistent with its failed efficiency ladder. Existing studies uturn_default_v1 and reverse_coarser_policy_v1/v2 already reject broad promotion of their alternatives; do not simply repeat those changes.

Next diagnostic: determine how much of the remaining gap persists when the research runner uses a single refinement level with a permissive local energy threshold, under the same geometry and native step size. This is an algorithmic ablation, not a proposed default or evidence of useful improvement. Preserve ordinary NUTS differences in turning, selection and divergence handling. No result is available yet.
