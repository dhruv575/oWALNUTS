# Bounded-prior market development screen

All 72 planned origin/cap cells completed with both methods qualified: 144 fits,
no omitted or replacement slots. This is 24 previously examined market origins
at three prior caps, not 72 independent market observations. All six full archives
passed exact-version S3 restore hashing and raw-joint reconstruction verification.
Coordinate and predictive diagnostics are preserved worker estimates; archive
verification did not independently recompute ArviZ diagnostics.

Mean WALNUTS-minus-baseline log predictive density, in nats per scored return:

| Prior cap | Rolling t5 | EWMA t5 | NIG AR1 |
|---|---:|---:|---:|
| 0.5 | 0.163252 | 0.085788 | 1.225324 |
| 1.0 | 0.164327 | 0.086863 | 1.226399 |
| 2.0 | 0.165586 | 0.088122 | 1.227657 |

These positive averages are not broad dominance. At cap 1, WALNUTS beats rolling
t5 at 9/24 origins, EWMA at 12/24 and NIG AR1 at 15/24. Median differences are
-0.05600, -0.00247 and +0.08877. Monthly mean differences at cap 1 are:

| Month | Rolling t5 | EWMA t5 | NIG AR1 |
|---|---:|---:|---:|
| December | 0.58028 | 0.29127 | 3.76057 |
| January | -0.07517 | -0.05012 | -0.12907 |
| February | -0.01213 | 0.01944 | 0.04769 |

December contributes the positive pooled result. Cap 1 is displayed for compact
description, not selected as a winner; the machine-readable summary retains all
caps and months. No uncertainty interval across independent markets is claimed.

Mean WALNUTS-minus-NUTS score differences across the 24 origins are +0.002191,
+0.000097 and -0.000037 for caps 0.5, 1 and 2. Maximum absolute per-cell difference
is 0.036806 nats. The maximum absolute difference divided by the quadrature sum
of reported log-score MCSEs is 2.650 over 72 comparisons, with none above 3.
This is descriptive agreement, not a simultaneous confidence guarantee or proof
of exact posterior fidelity. The study is not precision-matched speed evidence.

Next: retain every case, audit score uncertainty and tail influence, independently
recompute diagnostics for archived traces, and freeze a genuinely untouched
confirmation period before inspecting it. Economic inventory/cost assumptions,
counterfactual evaluation, mathematical review and a submission-ready paper
remain outstanding. These results do not establish profit or trading readiness.
