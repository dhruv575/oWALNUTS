# Checker API repair, no scientific change

The first predictive model compiled, but the checker stopped before comparing
any generated quantity because BridgeStan requires an RNG handle whenever
include_gq=True, even for deterministic generated quantities. Retain the full
failed build/check supervision and log. No scientific threshold failed.

A separate check02 loads the already compiled artifact (no rebuild), supplies
the required handle with seed951700002, and repeats the original frozen24points
and unchanged thresholds. The Stan generated quantities contain no RNG calls.
Record source/library hashes. One BLAS1 checker180s/3GiB/16MiB. This is a reviewed
API correction, not an automatic retry or a posterior/predictive result.
