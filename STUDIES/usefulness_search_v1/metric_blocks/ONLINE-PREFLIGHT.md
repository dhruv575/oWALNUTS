# Two-stage integration preflight

Frozen 2026-10-30 before runs. Research harness only, no library changes.
First verify the selector-to-public-fixed-matrix seam with Gaussian known targets.
The API uses momentum mass M; selector output is covariance C, so install M=C^-1.
This staged implementation restarts the random stream at the boundary. It is not
the existing single-run automatic handoff and makes no path-parity claim.

Targets: 3-dimensional precision identity, and precision with diagonal one,
P01=P10=.98 and other off-diagonals zero. Four chains start at fixed dispersed
positions [1,-1,1], [-1,1,-1], [2,2,0], [-2,-2,0]. Seeds 928300001--928300004.
Pilot: default diagonal sampler, 250 warmup plus 100 draws, ALL discarded from
inference. Four states per chain at indices 0,24,49,99. Central gradient Hessians
at h=1e-4*(1+abs(qj)) and half h. Charge 4*d calls per snapshot. Estimate marginal
variances by pooling within-chain pilot sample variances (ddof=1), floor 1e-8.
Apply unchanged v2 selector. Then invert selected covariance and call fixed_dense;
if no block, use fixed_diagonal reciprocal variances. Adapt step size only for
750 more discarded iterations; retain 2000 draws. Start at each pilot's last
state and use seed+100000. The pilot, probes and stage-two work all count.

Controls: default adaptive diagonal and full dense, 1100 warmup and 2000 draws,
same four starts and base seeds. This is a small correctness/mechanics screen,
not an efficacy gate. Check every candidate replicate: rank Rhat <=1.01,
bulk/tail ESS >=400; coordinate means within .12 target SD, coordinate SD relative
error <=.12, and whitened second moment spectral error <=.15. Report all arms
and all failures; no threshold tuning. Expected selector behavior: correlated
block [0,1], no independent block. No application or novel-method claim.

Build isolated source fixture, offline Cargo locked. Each job <=180 seconds,
sampled RSS <=2 GiB, output <=64 MiB. Sequential orchestration of four-thread
samplers initially, preserve raw draws and hashes, durable copies, private archive.
