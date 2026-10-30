# Broader screen: continuation gate passes, application claim remains open

Four fresh matched seeds on six reference-qualified models; 96 bounded jobs
completed with drained process groups. All 72 stage schedules, charged pilot/probe
costs and durable result hashes verified. Candidate v4 retains v3 full block shape
when selected and uses adaptive automatic fallback otherwise. This fallback policy
was frozen before this screen and is not applied retrospectively.

| Model | Candidate/dense/auto passes | Candidate ESS/calls vs dense | vs auto |
|---|---:|---:|---:|
| ARMA | 4/4/4 | .965 | .998 |
| arK | 4/4/4 | 1.178 | 1.313 |
| Proper-prior regression (sblrc) | 4/4/4 | 15.398 | 14.097 |
| Centered eight schools | 0/0/0 | unqualified | unqualified |
| GARCH | 4/4/4 | .721 | .998 |
| GP Poisson regression | 4/2/4 | unqualified | 1.000 |

Ratios are paired geometric means, not wall-time speedups. Sixteen fallback cells
match automatic adaptation exactly on all non-timing output; extra probes cost
slightly more. Only arK and sblrc select blocks. No paired accuracy loss against
auto was observed, but four seeds do not establish noninferiority. Eight-schools
mixing remains inadequate despite reference qualification. No ratios are credited
for failed baselines. The prespecified continuation gate passes on sblrc alone.

458-member evidence archive restored from its exact private S3 version and all
member hashes verified; see broad_archive/S3-VERIFICATION.json. Disk reclamation
removed only 192 verified redundant compressed results (58,646,348 bytes) from
prior studies; original raw results and independently verified archives remain.
Audit: broad01/RECLAIM-GZIP.json. No active dependencies removed.

## Model-specific shortcut changes the interpretation

A separately frozen collapsed-regression preflight integrates the five Gaussian
coefficients analytically and log sigma numerically, retaining both proper priors.
Both quadrature ranges pass: posterior marginal means/SDs agree within 1.52e-9
reference SD; means are within 1.38 reference MCSE and SD errors below .5%.
64 joint density/gradient checks pass (1.33e-12 centered density error, 4.98e-12
scaled gradient error). Setup .00054 seconds and integrations .0128--.0142 seconds
on this machine; these are moment calculations, not a sampler timing comparison.
Boundary densities underflow to zero, which is not a rigorous tail bound.

This makes sblrc a weak application case for general MCMC despite the large
adaptation gain. No IID generator is qualified by this preflight. Preserve the
algorithmic signal, then test less reducible targets and a qualified dense Fisher
baseline. Fresh larger replication remains necessary. No deployment, general
superiority, profitability or novel Hessian-preconditioning claim follows.
