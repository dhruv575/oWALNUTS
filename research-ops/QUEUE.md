# Active research queue

Updated 2026-10-28. Status requires live verification; this file is not a watcher.

1. **Running: E72 paired warm budgets.** Existing instance, four disjoint
   four-core workers. Root `/home/ubuntu/lanes/warm-budget-factorial-20261028`.
   At the latest verified observation, jobs 1/3/5/7 were advancing and the
   campaign had no terminal receipt. Read `pulse.py`, processes and terminal
   records before acting. Preserve the fixed 3600-second per-job limit even
   when a slower monthly path cannot finish. Do not restart on SSH timeout.
2. **Next: E72 terminal audit.** Verify process drain, all 12 job slots and all
   96 planned reference-spot slots. Preserve missing scores and failed reference
   flags. Reconstruct candidate scores and MCSE from sealed arrays; report each
   seed, each budget, full-path cost/health and paired differences. Separate
   partial-path timing from completed-path costs. Archive with a verified
   restore before reclaiming redundant output.
3. **Preparation while sampling: calibration design and comparator audit.**
   See `paper/CALIBRATION-DESIGN.md`. This is proposed work, not authorization
   to bypass readiness checks or alter the live campaign. Audit prior internal
   experiments before implementing a new synthetic study.
4. **Economic work remains necessary.** The accounting oracle is not a market
   validation. Define feasible actions, observed information, execution and
   controls before running a claimed AMM-profit study. Preserve the negative
   fixed-cost decision results; do not promote an exposed cost-sweep winner.

Paper checkpoint `f64777bf` contains all 44 fixed completed-study comparisons
and reproducible figures. Notification frequency remains approximately one
third of the earlier cadence; batch scientific milestones, not routine polls.
