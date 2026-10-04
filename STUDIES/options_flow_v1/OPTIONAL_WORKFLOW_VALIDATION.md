# Optional workflow correctness validation

The isolated worktree focused test invocation completed with exit code 0:
**28 passed in 42.96 seconds**. Other agents could run correctness tests
concurrently, so this duration is not a comparative timing measurement.

```powershell
$env:PYTHONPATH='C:/dev/owalnuts/target/python-flow-worktree/integrations/python/python'
& C:/dev/owalnuts/target/python-workflow-env/Scripts/python.exe -m pytest STUDIES/options_flow_v1/test_flow_mixed_coordinates.py STUDIES/options_flow_v1/test_mixed_flow_workers.py STUDIES/options_flow_v1/test_pymc_flow_continuation_workflow.py STUDIES/options_flow_v1/test_masked_market_comparison_plan.py STUDIES/options_flow_v1/test_masked_market_comparison_execute.py -q
```

The source implementation commits were `c0be9e5` (sparse planner/executor),
`f8e85f9` (mixed target) and `573c074` (opt-in workers). The isolated native
extension remained the attested release binary with SHA256
`e1331c8dabb4d5f8c3915b0ea7f699d6a7d4b49d05ee8282237a35a122429ac5`.

Verified contracts include:

- JAX64 full-Jacobian sign and normalized transformed-density gradients;
  public compiled target parity; batched physical-coordinate roundtrips and
  representable-scale boundaries.
- Tiny public and NumPyro mixed-coordinate fits preserve physical starts and
  exact canonical draw prefixes. Their expected failed health/precision gates
  remain failed. Existing dense and masked worker checks also pass.
- Sparse-market starts are dispersed at 0.25 prior standard deviation, not full
  prior draws. Placeholder normalization leaves observed likelihood inputs,
  observation masks and future labels unchanged.
- Independent executor gates retain every one of 108 canonical coordinates,
  fourteen functionals and 192 forecast cells. Changing labels or the sign of
  alpha does not select the precision family. Wrong horizons, missing-data
  scoring, callback disagreement, changing adapted state, continuation past the
  first passing tier, timeouts, missing reports, launch failures, stale sources
  and duplicate attempts are exercised.

No sparse-market fixture was prepared or frozen by this invocation. No market
posterior or long mixed-coordinate target was sampled. No scientific qualification,
calibration, broad reliability or performance improvement follows from these tests.
The optional targets remain opt-in and all earlier failed outcomes are preserved.
