# Demanding posterior resource pilot

This four-fit pilot measures whether independent reference-bank construction
is practical on the existing T1000/G4 posterior. It cannot establish endpoint
accuracy or bootstrap coverage with two fits per backend. Pilot draws are
excluded from the subsequent reference bank.

The authoritative plan is frozen from `plan-draft.json` after independent
review. Run order is public, reference, reference, public, with separate
initialization, sampler and predictive streams. The original fixture SHA-256 is
`2f9e39f9ac4fb91c20b9ef2015f923d916cab1462890af7fe611f3b7012268a6`.
Only initial positions change across fits; the posterior and forecast covariate
remain fixed. Public sampling uses the attested mixed-coordinate PyMC/CFunc
workflow with block size 32. The reference is associative mixed-coordinate
NumPyro with target acceptance .9, the strongest tested reference recipe.

Each fit has four chains, 1,000 warmup and exactly 8,000 retained draws. The
4,000-draw checkpoint is the exact prefix, not an independent fit or an early
stopping opportunity. Both checkpoints report all 1,012 canonical coordinates,
14 physical functionals and four observed forecasts, with R-hat at most 1.01,
bulk and tail ESS at least 400, zero retained divergences and endpoint MCSE
at most .02 interval widths. Resource completion does not imply these gates
pass; unhealthy results remain explicit.

The future accuracy family contains the .05/.95 endpoints of beta_bar, tau,
mu_h, sigma_h, h_terminal and the group-zero one-step observed return. The
predictive CDF uses the fixture's actual covariate and Student-t observation
noise, retaining the existing 16/32/64/128 quadrature checks. Numerical
convergence is not proof of posterior accuracy.

Each fresh contained process runs on CPU 0 with an 8-GiB process committed
memory cap and 1,800-second wall cap. The controller allowance is 7,200 seconds,
including a 15-second cleanup reserve. Costs include admission, compilation,
adaptation, sampling, serialization, extraction, full diagnostics and predictive
integration. Worker peak CPU/memory excludes compiler-child aggregate usage;
contained elapsed time includes child work. Controller overhead and any final
bookkeeping overrun remain measured. No overlapping numerical jobs or retries.

All four intended outcomes, failures and unstarted fits remain recorded. Raw
JSON and extracted arrays stay local with hashes; compact results and source
provenance are archived. The preparation directory preserves byte-identical
copies of externally bound audit inputs for restoration. Earlier audit drafts
are retained; v3 is the plan's effective audit. The contained CLI validation
exercises admission failure and cleanup, not a successful sampling fit.

Use measured costs to design a separate, fresh bank of 16–32 independent fits
per backend, preferably 32. Report achieved reference uncertainty and preserve
its shared contribution across candidate comparisons. No exact-truth claim,
automatic tolerance relaxation, replacement of failures or automatic reduction
of the demanding uncertainty-estimation objective follows from this pilot.
