# Local scaffold status (not an executed study)

Files implement generation functions, causal window indexing, dependency-injected
stream orchestration, posterior-only resident refresh (no quantile roots), exact
cheap baseline, observed-return evaluator bridge, independent nutpie adapter,
positive-density logscore MCSE scaling, and a POSIX process-group watchdog.
No study data, native posterior samples, predictive outcomes or AWS work were
produced. Ten tests use literal arrays, mocks and a fake RNG that never draws.
They verify283-value indexing, current-latent oracle restriction, full failure
accounting, no retries, session poisoning, log(mean density) MCSE distinction,
causal baseline input shape and refusal to execute a draft watchdog manifest.

Evaluator integration is explicit: wp97's evaluate_observation(draws,y,rho=.95,
nu=5,orders=(64,128),chunk=512,deadline=time.monotonic()+cap), mapping pit to cdf.
The source hash must be passed from the future frozen manifest. No global numerical
backend mutation or order reduction. Oracle uses a single true-parameter/current-h
component and the SAME next-innovation integral, never future latent truth.
The density evaluator's per-draw scaled-density outputs retain chain axes for
chain-aware MCSE; fitting code must not replace them with logdensity MCSE.

Still blocked before any real study execution:
- Final reviewed evaluator/reference source/runtime hashes and fixed input fixtures.
- Installed nutpie API/compiler/target/seed validation with full beta extraction.
- Final reference settings/MCSE diagnostics and numerical-failure evidence format.
- A durable1024-row aggregate ledger, cluster-bootstrap reporting implementation,
  explicit per-stream/global budgets and a complete evidence validator.
- A frozen authorized run manifest; watchdog currently cannot mark mere exit0 as
  complete evidence and no study CLI invokes generation/sampling automatically.

Generation failure records must preserve failed stream IDs and available parameter
metadata; the generator raises and never retries. Per-stream failures preserve
attempted rows and unattempted ticks. Future aggregate orchestration must continue
other predeclared streams only within the fixed cap; it must not silently shorten
or replace the32-stream population. Current scaffold is reviewed code groundwork,
not a claim that the study is ready to launch.

Tests executed locally with
C:/dev/owalnuts/target/python-workflow-env/Scripts/python.exe -m unittest discover
-s STUDIES/prior_predictive_validation_v1 -p test_scaffold.py -v
Ten passed in0.013s; no sampler module was imported by these fixtures.
