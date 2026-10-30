# Saved-pilot fallback and established-criterion audit

Frozen before audit execution; post-hoc hypothesis development, not validation.
Read all96 hybrid pilot/fit cells, preserve input hashes. For the16 proper-prior
regression cells, compare installed v4/Fisher covariance against unconstrained
reference covariance. Record diagonal scale ratios, whitened condition proxy,
and a diagnostic reconstruction using Fisher diagonal scales with the unchanged
stable-curvature block shape. This proxy is not ESS or application evidence.

Evaluate Bales et al.(2019), Eq13, on four held-out-chain folds per cell. Train
Fisher, diagonal, empirical and stable-block metrics on the other three chains;
score using held-out covariance and its four saved Hessian snapshots. Compute
maximum over snapshots, then maximum over folds. No new target calls. Keep all
models, failures and scores. No threshold optimization or sampler performance
credit for selecting a new metric. This uses the published criterion with a
different split/candidate set; it does not replicate its full published schedule.
Neither fixed diagonal nor fixed empirical is equivalent to adaptive auto/dense.

Before audit, check exact Gaussian criterion1 for true covariance, covariance
scale invariance, coordinate permutation, and rejection of non-SPD inputs.
Bound worker180s/2GiB/64MiB, preserve source, reports, hash lineage and supervision.
https://arxiv.org/html/1905.11916v3 (sections3.1 and4).
