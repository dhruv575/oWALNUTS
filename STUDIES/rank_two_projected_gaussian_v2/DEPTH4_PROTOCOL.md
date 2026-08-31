# Depth-4 intervention

Frozen before execution on 2026-08-30 after the stop audit.

Seeds 75001--75004. The sole sampler change from the stop-audit replay is
maximum depth 3 to 4. Target, starts, pooled rank-two adaptation, warmup=180,
retained=300, windows, step search, and mixing gates are unchanged. Preflight
must be zero-callback. Every chain must be finite/nondivergent and the true
maximum-depth rate must be at most 1%; geometric ESJD and lag-one inefficiency
improvements must each remain at least 1.05. No T=1000 execution is authorized.
