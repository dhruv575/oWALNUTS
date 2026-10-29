# Likelihood-cost mechanism experiment, 2026-10-29

The fresh-seed depth-eleven follow-up supports the proposed evaluation-cost
mechanism on this controlled model: WALNUTS is **1.93x faster than diagonal
NUTS** and **2.56x faster than low-rank NUTS** in matched native kernel time,
with **8/8 qualifying seeds for every arm**. Cold total-time gains are 1.82x
and 2.40x. The original depth-ten screen did not meet its qualification rule
and remains reported separately below. This is exploratory follow-up evidence,
not a broad application-level confirmation.

The primary screen measures a larger WALNUTS speed lead as the common full
likelihood becomes expensive, but fails its predeclared qualification rule.
At 2,048 observations, qualified-pair native kernel speed is 1.88x versus
diagonal NUTS and 2.40x versus low-rank NUTS. WALNUTS qualifies 6/8 seeds,
below diagonal NUTS's 8/8. Every disqualification is due solely to one or two
retained depth-limit hits; all exact accuracy, MCSE, R-hat, ESS and divergence
checks pass. These depth hits do not demonstrate wrong posterior estimates.

The optimized controls decisively outperform full-likelihood sampling. This
controlled Gaussian regression has an analytic posterior and does not need
MCMC. A speed lead over its uncollapsed likelihood is evidence about an
evaluation-cost mechanism, not a unique or practically optimal use case.

## What was tested

The [protocol](../PROTOCOL.md) was frozen at `16be9fa1`. Two datasets have 64
and 2,048 independent observations with 24 coefficients and a Gaussian prior.
Both engines evaluate the actual dense regression likelihood and gradient;
there are no artificial delays or duplicated dummy likelihood terms.
Analytic affine normalization followed by the curvature-five pair transform
holds posterior geometry fixed. This deliberately constructed model isolates
likelihood cost; its full evaluator has an available sufficient-statistic
shortcut, which is explicitly included as a control.

Eight fresh seeds per arm and dataset, four chains, 750 warmup, 6,000 retained
draws, maximum depth ten, common native density code, single-thread BLAS and
shuffled job ordering produce 80 fits. WALNUTS uses the previously calibrated
acceptance .90/error1 setting. NUTS uses .99 with gradient-diagonal or low-rank
mass. No settings were selected on these new outcomes. All 80 fits completed
and drained successfully in 282.24 seconds on the existing instance.

## Primary fixed-budget results

Times below are medians across all eight completed fits, including fits that
did not qualify. Kernel time includes materializing the reparameterized draws.

| Observations | Arm | Qualified /8 | Kernel seconds | Cold total seconds |
|---:|---|---:|---:|---:|
| 64 | Full WALNUTS | 6 | 6.14 | 11.19 |
| 64 | Full diagonal NUTS | 8 | 8.63 | 13.59 |
| 64 | Full low-rank NUTS | 4 | 21.48 | 26.47 |
| 64 | Collapsed NUTS | 6 | 2.47 | 7.13 |
| 64 | Reparameterized NUTS | 8 | 0.229 | 4.72 |
| 2,048 | Full WALNUTS | 6 | 40.77 | 45.80 |
| 2,048 | Full diagonal NUTS | 8 | 77.18 | 82.26 |
| 2,048 | Full low-rank NUTS | 5 | 99.63 | 104.61 |
| 2,048 | Collapsed NUTS | 7 | 2.43 | 7.05 |
| 2,048 | Reparameterized NUTS | 8 | 0.230 | 4.77 |

Paired successful-only diagonal-NUTS/WALNUTS kernel ratios rise from 1.43
[1.36,1.54] at 64 observations to 1.88 [1.77,2.07] at 2,048; both use six
qualified pairs. At the larger size, the low-rank comparison is 2.40
[2.29,2.49] on only four qualified pairs. These are exploratory bootstrap
intervals with explicit complete-pair selection, not unconditional speed
guarantees. The larger-size diagonal cold-total ratio is 1.78 [1.69,1.95].

At 2,048 observations, median target calls are 3.75 million for WALNUTS,
7.63 million for diagonal NUTS and 8.76 million for low-rank NUTS. This is
consistent with fewer expensive evaluations producing a wall-time benefit.
Floating-point evaluation and distinct sampler seeds can change trajectories;
the study holds the exact posterior geometry fixed, not bitwise trajectories.

The full primary rule required at least 7/8 qualified WALNUTS seeds, no fewer
than either full NUTS arm, and >=1.5x speed over both with interval lower
bounds above one. Qualification fails. The four WALNUTS failures across the
two datasets each have exactly one retained depth-ten hit. No failures are
dropped, relabeled or replaced.

## Fresh-seed depth-eleven follow-up

After the primary screen, [a separate protocol](../depth_followup/PROTOCOL.md)
was frozen at `670e24ca`. It increased maximum depth to eleven for all three
full-evaluator arms, retaining the zero-depth-hit gate and every other setting.
It used eight fresh seeds per arm at n2048, shuffled jobs and the same resource
bounds. It did not retry only failed seeds. No further escalation was allowed.
All 24 fits completed and drained in 217.86 seconds. All accuracy, MCSE,
R-hat/ESS, divergence and new depth-eleven gates pass on all eight seeds per arm.

| Full likelihood arm | Qualified /8 | Median kernel seconds | Median cold total seconds |
|---|---:|---:|---:|
| WALNUTS | 8 | 39.87 | 44.83 |
| Diagonal NUTS | 8 | 76.76 | 81.85 |
| Low-rank NUTS | 8 | 104.46 | 109.55 |

Paired median diagonal-NUTS/WALNUTS kernel ratio is **1.926** with exploratory
95% interval **[1.834,2.007]**; total-time ratio **1.824 [1.736,1.895]**.
Low-rank ratios are **2.565 [2.487,2.677]** for kernel time and
**2.397 [2.325,2.484]** for total time. Every comparison uses all eight pairs.
The corresponding target-call ratios are **2.048 [1.942,2.134]** and
**2.392 [2.334,2.523]**. Thus the full follow-up mechanism rule is met.

The follow-up changes a trajectory budget, not the acceptance criteria, and
does not establish that the earlier estimates were wrong. Its interpretation
is specifically a fresh-seed response to an exposed depth-limit issue. It
does not retroactively convert the original primary study into a success.
Optimized controls below come from the primary screen; no superiority over
those controls is established or claimed.

## Analytic control

The [IID supplement](../IID-SUPPLEMENT.md), specified before inspecting primary
outcomes, draws directly from the analytic posterior. All 16 cases qualify.
Generating and mapping four chains of 6,000 independent draws takes median
0.0066 seconds at n64 and 0.0065 seconds at n2048. Analytic setup takes roughly
0.00031 and 0.00098 seconds, respectively. These component costs exclude
amortized process imports, diagnostics and serialization; they are not cold
worker totals. Direct sampling and reparameterization prevent any claim that
WALNUTS is the best inference method for this regression.

## Reproducibility and limitations

The main source, seeds, exact X/y datasets and posterior parameters, native
adapter, all raw double-precision draws, metrics, and resource receipts are
preserved. Five validation tests pass for each frozen source version, covering dense-versus-analytic values,
finite-difference gradients, native ABI values/recoverable overflow, all five
sampler arms, exact functionals, and complete-pair analysis. A premature
analysis invocation correctly refused to run before FINAL.json existed; it
created no partial report and did not affect the experiment.

Eight seeds and one dataset per size provide limited generalization. The
normalization uses analytic posterior structure, and all optimized shortcuts
are intentionally visible. This is not a nonlinear application benchmark,
AMM success, decision-value result, profitability claim or uniqueness result.
No global library defaults, deployments, or trading behavior were changed.

Raw archive: `target/likelihood-cost-evidence-v1.tar.gz`; see
ARCHIVE-VERIFICATION.json. Original EC2 evidence remains under
`/home/ubuntu/lanes/likelihood-cost-20261029`. S3 upload remains pending renewal
of the previously expired local AWS login. Backup streams directly to the
local archive to avoid a second EC2 tar copy. A previously verified redundant
pivot transfer tar was checksum-reverified locally and remotely before removal;
the pivot run originals and local archive remain intact.

All **480 archived files**, both executed-source freezes, and all four IID
supplement source hashes verified. The saved X/y files match the data hash
recorded by every one of the 104 sampler fits. Archive SHA256:
`580858248390cdf6057d7bbefc98b9525787898a9881c7c42ac5ba2d57f26383`.
The instance remains running. Final free root disk was 1,086,537,728 bytes,
only about 13 MB above the admission reserve; another on-disk campaign needs
archive/reclamation headroom first.
