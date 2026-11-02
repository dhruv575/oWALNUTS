oWALNUTS 0.4.0 adds reusable warm sessions and streaming functionals, incorporates
sampler storage and diagnostic optimizations, and enables the documented
trapped-chain warmup safeguard.

- Continue or retarget sampling with warm states and resident sessions.
- Compute functionals while sampling, with optional retention of full draws.
- Use the trapped-chain safeguard and its telemetry; opt out through the
  adaptation configuration when reproducing earlier behavior.
- Receive the current allocation, metric-scratch and diagnostic improvements.
- Includes dependency-lock and cross-platform test/lint repairs.

Performance remains workload-dependent. The completed hierarchical-binomial
study did not establish broad superiority over carefully tuned NUTS: one hybrid
case favored WALNUTS and another favored NUTS. The rebuilt sampler was only
slightly faster than the previously installed binary in that study. No10x,
unique-application, profitability or general-purpose performance claim is made.

See CHANGELOG.md for API details and
STUDIES/funnel_application_v1/LATEST-BUILD-RESULTS.md for protocols, baselines,
negative results and the final fresh-seed replication.

Install with `pip install --upgrade owalnuts==0.4.0` after publication.
Python3.10+ wheels and a source distribution are built and tested by the release
workflow. Rust package publication is not part of this release operation.
