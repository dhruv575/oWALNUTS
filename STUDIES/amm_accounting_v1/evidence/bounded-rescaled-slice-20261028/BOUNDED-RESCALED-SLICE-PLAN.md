# Independent rescaled-coordinate all-zero control

Fixed T=12,y=0,rho=.95, caps .5/1/2, four chains each. The scientific target is
unchanged from the bounded-scale panel. Gaussian-reference coordinates are
standardized mu, the truncated-lognormal prior quantile w, auxiliary b, and z.
Physical beta=exp(mean(h)/2)*b. The residual density includes the physical beta
prior, the mean(h)/2 Jacobian and cancellation of the artificial N(0,1) b
reference. It does not replace the physical beta prior with a prior on b.
Ten deterministic tests verify the full density change of variables and a
finite, nonmutating transition. An initial local file-generation command failed
before creating the module; after correction all tests passed. No sampling was
performed by that failed command.

Each chain starts at zero Gaussian-reference coordinates, then runs 1,000 warmup
and 4,000 retained sweeps, with scalar mu/w/b blocks and one 12-coordinate z block.
This differs from NUTS's prior-median scale initialization, as disclosed in the
earlier slice panels. Ellipse attempt cap 1,000; abort rather than silently retain
an invalid step. Twelve seeds 398137000..398137011, audited before launch. No
replacement seeds, initialization changes or budget extensions after inspection.

Twelve concurrent one-core chains on cores 0..11. Per-chain 600seconds, 1GiB RSS,
64MiB output; outer 660seconds, 14GiB RSS,512MiB output; admission 1GiB free disk.
Preserve complete warmup and retained physical arrays, work counts, source
bindings, seed inventory and supervision, including every failure.

Compare physical mu,log_sigma,beta,z against the frozen reparameterized NUTS
archive 5d7919aed5de70f8f1452caced7d1f4bd162e6aa53e8a98c8a9c36dbaa2c9c3c.
Require all Rhat<=1.01, bulk/tail ESS>=400 for each method before calling a
comparison independently qualified. Report mean differences with combined MCSE,
without treating a maximum-over-coordinates threshold as simultaneous coverage.
Passing does not justify a prior cap or establish market/economic validity.
