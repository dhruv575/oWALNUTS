# Changelog

All notable changes to oWALNUTS will be documented here.

## [0.1.0-beta.1] - Unreleased

### Added

- Minimal standalone `owalnuts` crate containing the fixed-diagonal internal-beta facade.
- Bounded Gaussian example, facade tests, resource controls, telemetry, and run identity metadata.
- Private parity tests and pinned upstream oracle fixtures with provenance.

### Fixed

- **Micro-step acceptance statistic (kernel revision `v9`).** Through `v8` a
  refinement level was accepted when the largest Hamiltonian departure of any
  visited micro-step from the start state was within `max_error`. That
  statistic is not symmetric under time reversal, so the deterministic reverse
  selection could disagree with the forward selection and non-reversible leaves
  were accepted; on Neal's 10-D funnel at the paper's tuning the kernel placed
  about twice the correct mass below `omega = -5`. Acceptance now uses the
  endpoint departure `|H(end) - H(start)|` exactly as upstream
  `walnutpie::macro_step`/`within_tolerance`. Runs that never refine are
  unchanged; every prior result from a refinement-active run should be treated
  as provisional until re-run. Verified by a 4,000-leaf funnel differential
  oracle generated from the unmodified upstream headers
  (`oracle/walnutpie/f5bba365_funnel_leaves`) and by
  `STUDIES/funnel_bias_fix_v1` (P(omega<-5) 0.0474 vs exact 0.0478 at
  4x50,000 draws; `v8` gave 0.0971).
- The pinned upstream macro-leaf oracle no longer carves out
  `forward_refinement`, `backward_refinement`, and
  `multi_level_reverse_coarsening`; all pinned cases pass unmodified.

### Removed

- Legacy weighted sampler, NUTS, Python, benchmark, and prototype public surfaces.
