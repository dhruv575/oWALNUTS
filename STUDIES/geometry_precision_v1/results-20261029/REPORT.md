# Known-truth geometry screen, 2026-10-29

The initial screen found a narrow precision lead on a curved banana target,
but no target met the declared 1.5x cold total-cost advantage rule. This is
exploratory computational evidence, not decision value, profitability, or a
general claim of uniqueness. Calibration selections were frozen before held-out
evaluation. All negative results are retained.

## Original held-out screen

126 calibration fits selected one configuration per engine and target. The
held-out screen ran 432 fits: nine targets, two engines, eight seeds, and three
independent budgets (250, 1,000, 3,000 retained draws per chain). Four chains,
750 warmup iterations, depth ten, and identical deterministic initial states
were used. Every held-out fit executed successfully.

Qualification requires known-truth functional error limits, MCSE no more than
half those limits, R-hat <=1.01, bulk/tail ESS >=400, and zero retained
divergences or depth-limit hits. See the frozen [protocol](../PROTOCOL.md).
Ladder costs include unsuccessful smaller budgets; unsuccessful ladders remain
censored. Eight seeds provide limited precision and no broad domain inference.

| Target | NUTS qualifying ladders /8 | WALNUTS /8 |
|---|---:|---:|
| Isotropic Gaussian | 8 | 8 |
| Correlated Gaussian | 8 | 0 |
| Curved banana | 0 | 8 |
| Moderate funnel | 0 | 0 |
| Severe funnel | 0 | 0 |
| Noncentered funnel | 8 | 8 |
| Changing conditional scale | 0 | 0 |
| Student t | 8 | 8 |
| Separated mixture | 0 | 0 |

The banana NUTS estimates were within the exact error tolerances and passed
conventional diagnostics. Only the stringent MCSE gate failed, by approximately
1–17%. WALNUTS passed all eight at 3,000 draws, but used more target evaluations.
This motivated the separately frozen native-backend follow-up below.

On isotropic, noncentered, and Student t targets the median NUTS/WALNUTS cold
total-cost ratios were only 1.06, 1.10, and 1.07. Sampler-only ratios were 2.53,
3.13, and 1.41, respectively, despite no target-call advantage. Python dispatch
and setup materially affect the interpretation of these timings.

## Controls and repeated updates

Independent exact draws passed all nine targets on all eight seeds at 3,000
draws. Thus the precision criteria are achievable. Laplace passed all eight
seeds on the three Gaussian parameterizations and none on the six non-Gaussian
targets. These are exact finite-dimensional controls, not a general dismissal
of Laplace on realistic applications.

Warm continuation did not establish a speed advantage. On smooth banana
updates it qualified 4/4 six-update streams, versus 2/4 for cold WALNUTS, at
median total costs of 60.3 versus 23.9 seconds. Abrupt banana shifts qualified
only 2/4 warm streams. Correlated Gaussian warm WALNUTS qualified 0/4 streams
on either path; cold NUTS qualified 4/4. Initialization is charged to warm costs.
This supplement used Python callbacks and lacks a warm NUTS comparator, so it
cannot establish a unique continuation capability.

## Corrected native follow-up

All 96 corrected fits completed. Both engines used native callbacks around the
same compiled target and analytic gradient. The follow-up was selected after
the banana screen and is exploratory; its larger budgets and stronger NUTS
settings were frozen before execution.

| Configuration | Pass /8 at 3,000 | At 6,000 | At 12,000 | Median native kernel seconds at 3,000 |
|---|---:|---:|---:|---:|
| WALNUTS, acceptance .99 | 8 | 8 | 8 | 0.442 |
| NUTS, acceptance .99 | 1 | 7 | 8 | 0.164 |
| NUTS, low-rank .99 | 5 | 8 | 8 | 0.466 |
| NUTS, draw-based mass .99 | 6 | 7 | 7 | 0.216 |

Every configuration qualified all eight ladders at some budget. WALNUTS's
precision per retained draw survives the corrected native check. Its broader
cost advantage does not survive stronger controls: median paired total ladder
cost ratios NUTS/WALNUTS are 1.97 (ordinary), 1.05 (low-rank), and 0.98
(draw-based mass). Exploratory 95% bootstrap intervals are [1.89,2.08],
[0.99,2.08], and [0.95,1.92]. The corresponding kernel-cost ratios are 1.01,
1.30, and 0.53. Coarse restart ladders charge repeated initialization and are
not optimal adaptive stopping policies. These results do not establish the
declared 1.5x advantage against the stronger baselines.

At 3,000 draws WALNUTS used median 782,936 target calls versus 383,461 for
ordinary NUTS. Its rejected nonfinite proposals are counted (22 across the
eight 3,000-draw fits); successful fits still pass the retained divergence gate.
Native-v1 failure counts are invalid evidence about sampler reliability.

The useful research lead is curved, non-Gaussian geometry where Laplace fails
and WALNUTS provides more precision per draw. It needs a stronger practical
cost argument before motivating a pivot. A next bounded study should vary
curvature and dimension with fresh seeds and include native NUTS mass controls,
direct fixed-budget costs, and an exact reparameterization baseline. Do not
scale an application campaign based solely on this selected toy target.

## Reproducibility and limitations

The source freezes, deterministic seeds, raw draws, resource receipts, failed
runs, and full diagnostic rows are preserved. The initial native preflight
encountered a conservative target-call admission bound; it was removed before
the native campaign, which retained wall-time and memory bounds. A subsequent
test invocation omitted PYTHONPATH and failed to import targets; the corrected
invocation is recorded in VALIDATION.txt. Neither is a sampling result.

The original native adapter incorrectly made overflowing WALNUTS proposals
fatal while NUTS could reject them. All 17 failures in native-v1 are preserved
as adapter failures. Native-v2 corrects the ABI handling and repeats all 96
cases at the original seeds; it is not a fresh independent replication.

This screen selects mathematical geometry rather than a business use case.
It does not establish a practical AMM win or a submission-ready novel claim.
Do not select a favorable seed, drop failed budgets, or report Python-interface
speed as an algorithmic reduction in work.

Validation: all 14 tests passed in the pinned EC2 runtime (target mathematics,
supplement controls, cost/censoring analysis, and native ABI including proposal
rejection). Raw archive: `target/geometry-precision-evidence-v1.tar.gz`, SHA256
`40897ff2a2fa8b7de1fd3e54fb752f4491c57f354edb68dba681da9fc32befb6`.
See `ARCHIVE-VERIFICATION.json` for complete member and executed-source checks.
EC2 originals remain under `/home/ubuntu/lanes/geometry-precision-20261029`.
S3 upload remains pending renewal of the previously expired local AWS login.
The instance remains running. Last observed memory availability was about
30 GiB. After local verification, the redundant EC2 transfer tar was removed
with a checksum-checked audit receipt, restoring 2.50 GB free disk. Original
EC2 run evidence was retained. All 4,030 archive members, seven executed-source
freezes, and six committed row files verified successfully.
