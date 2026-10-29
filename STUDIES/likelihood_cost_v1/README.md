# Likelihood cost mechanism test

Read [PROTOCOL.md](PROTOCOL.md) and [IID-SUPPLEMENT.md](IID-SUPPLEMENT.md).
The two dense regressions have identical analytically normalized curved
posterior geometry. They isolate evaluation cost, while the collapsed,
reparameterized, and IID controls show the available analytic shortcuts.
This is not a claim that these regressions require MCMC.

The archive preserves a frozen Linux `source` directory, `data` with X/y and
posterior parameters, raw draws, seeds, resource receipts and runtime versions.
With that layout and the recorded Python environment:

```sh
cd source
OPENBLAS_NUM_THREADS=1 python -m unittest test_study
OPENBLAS_NUM_THREADS=1 python analyze.py ../test-v1 ../new-analysis
```

The selected depth-eleven follow-up is frozen separately in `source-depth11`;
run its analyzer against `../depth11-v1`. Its protocol and fresh seed schedule
are in [depth_followup/PROTOCOL.md](depth_followup/PROTOCOL.md). Preserve the
primary depth-ten outcome alongside this follow-up.

Do not overwrite any original run or selection. `sampling.py` and `native.py`
reuse the previously verified adapter and sampler configuration path; the new
target tests check actual dense likelihoods against independent analytic
posteriors, finite-difference gradients, and native ABI values.

`receive_archive.py` streams the archive to the local target directory, checks
every member against a remotely generated manifest, verifies executed-source
hashes, and exports compact result rows. The supplemental IID process amortizes
imports, so its component costs must not be presented as cold-worker totals.
