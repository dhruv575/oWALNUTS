# Preregistered pooled rank-two Gaussian diagnostic

Frozen before execution on 2026-08-30.

This changes only the adaptive arm of `rank_two_projected_gaussian_v1`: four
chains pool projected Welford summaries at common boundaries and install one
shared metric. Target, seeds (71001--71004), starts, warmup (180), retained
draws (300), windows (30/50/30), boundary-search configuration, baseline, and
gates are unchanged.

Every paired chain must have no divergence and no maximum-depth stop. Every
window must install a rank-two candidate. Geometric mean normalized ESJD and
lag-one inefficiency must each improve by at least 5%. Only if all gates pass
may a fresh `T=1000`, `authorized_sampling=false` manifest be written; it must
not be sampled.
