# Depth-5 target-acceptance intervention

Frozen before execution on 2026-08-30 after trace replay.

Seeds 78001--78004. The sole tuning change is warmup target acceptance 0.8 to
0.9 in both adaptive and baseline arms. Depth=5, target, starts, pooled metric
adaptation, warmup=180, retained=300, windows, draws, and all depth-5 gates are
unchanged. This is motivated by identical adaptive/baseline transition-1
refinement exhaustion with delta-H 1.19e3--2.68e5 during initial-fast dual
averaging. Preflights must remain zero-callback.
