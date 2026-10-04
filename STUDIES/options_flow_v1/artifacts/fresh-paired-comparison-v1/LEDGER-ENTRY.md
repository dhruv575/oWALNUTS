# Ledger

1. Pre-execution: froze 36 matched pairs with alternating backend order,
   shared physical starts within pairs, independent sampler/prediction streams,
   full first-pass health/precision gates, and separately stated accuracy,
   reliability and runtime decisions. The reference bank is recorded in commit
   `802cdd0`. All 54,176 independent prelaunch checks passed; 78 harness tests
   passed. These establish readiness, not sampler performance. Preserved initial
   preparation/verifier failures and their documented corrections. Next decision:
   run every intended fit once, retain failures and all costs, then evaluate
   against the prospectively frozen joint reference uncertainty.
