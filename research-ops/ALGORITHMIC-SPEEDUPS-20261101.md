# Algorithmic speedups: all four directions investigated

The strongest result is exact grid algebra for the spatial GP. Three native
grid NUTS pilots finished in 21.9–22.9 seconds per four-chain job, including
imports and physical diagnostics, with min bulk ESS 2272–2304, R-hat <1.002,
zero divergences and zero depth hits. The matching completed original-Stan
control took 654.7 seconds and achieved min bulk ESS 1044. Its other seed hit
the predeclared 900-second limit; it is retained as a timeout, not a success.

For the one completed same-seed comparison, this is **29.8x lower worker wall
time (96.6% less time)** and **37.5x faster sampling**. Both have four chains,
1000 warmup, 2000 retained, target acceptance .99 and depth limit 12. The
coordinate system and initialization differ. These are pilot results, not
a universal sampler or application speedup. Compilation is a separate
one-time cost and is excluded from both worker timings.

## Findings

| Direction | Evidence | Decision |
|---|---|---|
| Exact grid algebra | 200x200 covariance handled through 20x20 and 10x10 factors; native evaluation about 51 microseconds, versus about 1.57 milliseconds for compiled Stan on the fixed probes. Three short native runs pass; one longer run also passes. | Highest priority. Continue independent reference and scaling validation. |
| Blocked spatial inference | Grid version cuts sampling from 46.1s to 3.7s relative to its dense equivalent, but all six blocked runs fail: worst R-hat 2.60, min bulk ESS around 5. Four field sweeps do not fix the geometry. | Reject this configuration despite cheap iterations. |
| Corrected physics proposals | Delayed acceptance remains exact in the numerical balance check, but calls the full target on about 88% of proposals. With transport, 0.61s sampling versus 0.66s for ordinary independent MH; full times 3.41s versus 3.44s. Untransported variants fail at least one gate. | Valid, but no large gain on this cheap two-parameter ODE. |
| Frozen nonlinear transport | A separately trained cubic conditional map takes 0.042s; importance ESS 1186/4096. Both native engines and both corrected-MH variants pass at the initial budgets. Raw/affine native controls need the longer precision followup. | Useful geometry improvement; do not attribute it uniquely to WALNUTS. |

Physics NUTS at the tested passing budgets takes 2.43s total with transport
(1000 retained), 3.52s affine (4000), and 4.36s raw (4000): approximately 1.45x
and 1.79x total improvements. Sampling-only ratios are 3.64x and 6.70x. At the
same 4000 draws, transport is only 1.32x faster in sampling and 1.07x in total
than affine. Two seeds and two discrete budgets do not identify the exact
minimum cost to meet accuracy. Forecast summaries, parameter means, MCSE and
convergence are checked against the existing qualified nonlinear quadrature.

## Numerical and posterior checks

The grid retains the original 1e-10 jitter and mathematical physical posterior.
It uses the unique symmetric covariance square root and a Sylvester derivative,
avoiding eigenvector differentiation. Its whitening differs from Stan's
Cholesky whitening. Native versus Python density and gradients pass at 24
fixed/random probes, including rho=4; maximum normalized finite-difference
error is 5.1e-7. Covariance reconstruction passes to about 1e-14.

The first cross-Stan check missed its density gate because independently
forming a nearly singular Cholesky factor amplified conversion error. The
preserved followup uses the actual compiled Stan factor; the fixed-probe
check passes narrowly. More importantly, a separate audit of 32 posterior
draws, including large-rho and large-alpha draws from each native job, passes
all original gates, with maximum Stan density discrepancy below 9.3e-7.

Short spatial runs do not all meet the strict historical pairwise agreement
gate of 0.05 pooled SD, even when discrepancies are consistent with their
MCSEs. A prespecified followup at 4000 draws finishes in **36.0s total**, with
min bulk ESS **4606**, and passes the mean/SD/MCSE agreement gates against the
completed new Stan control and **all four historical reference groups**.
The historical combined reference remains unqualified; these checks do not
retroactively qualify it. No spatial heldout data was used, and no prediction,
decision-value or profitability claim is made.

## Operations and reproducibility

Used only the existing c7a.4xlarge, with at most 12 reserved CPU slots, one BLAS
thread per worker, 2GiB RSS and 900-second job caps. Existing libraries were
reused. No new instance, deployment, cleanup or trading action occurred.
The completed lane occupied about 173MB; free disk was 1.25GB, above the 1GiB
floor. Preserve the second baseline timeout and all import/serialization
repairs; each repair is separately documented in the study.

All 271 files in the completed evidence snapshot were downloaded and verified
against remote SHA-256 hashes, including raw draws. The compressed archive and
raw arrays are excluded from Git, while protocols, sources, summaries,
supervision, logs and the verification manifest form the checkpoint. The
unrelated options-flow edit was left untouched.

Sources and full tables: `STUDIES/algorithmic_speedups_v1/` and
`STUDIES/algorithmic_speedups_v1/analysis01/RESULTS.md`.

The mathematical ingredients are established methods, not a claimed new
invention: [elliptical slice sampling](https://proceedings.mlr.press/v9/murray10a.html),
[structured grid GP computation](https://proceedings.mlr.press/v37/flaxman15),
[corrected surrogate proposals](https://arxiv.org/abs/2009.03699), and
[transport-map sampling](https://arxiv.org/abs/1412.5492). Any paper contribution
must distinguish this implementation and its evidence from those prior ideas.
