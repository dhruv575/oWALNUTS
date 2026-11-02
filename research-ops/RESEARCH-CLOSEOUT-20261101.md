# Research closeout

Dhruv instructed: finish the research, deploy the latest build, and turn off AWS.
This revokes the previous standing instruction to keep experiments running.
AGENTS.md now records the override. No new experiments or queued replications.

The final32-fit hybrid replication completed and all outcomes were preserved.
Both samplers passed8/8 seeds per case. Sampling medians: concentration10x,
NUTS .796s and WAL .628s; concentration100x, NUTS .795s and WAL1.405s.
This confirms geometry-dependent results, not a broad speed advantage.
See STUDIES/funnel_application_v1/LATEST-BUILD-RESULTS.md.

All eight funnel-study archives and every member hash were verified locally.
FUNNEL-CLOSEOUT-ARCHIVES.json records exact paths, sizes and SHA256 values.
This includes raw draws, failure evidence, source and old/new native binaries.
Every RAM-backed research lane has completed and has an archive manifest;
FUNNEL-CLOSEOUT-INVENTORY.json records the inventory. There is no ubuntu crontab.
Existing root-disk evidence must remain on EBS; stop, do not terminate/delete.

AWS target: account712710405275, us-east-2, i-05c712c79c74ae7f8,
18.223.111.36. CLI profile owalnuts is expired. The instance role is an archive
role and cannot describe EC2 shutdown behavior. Browser host is unavailable.
At this checkpoint shutdown is pending AWS login confirmation, not completed.
Do not claim a disconnected SSH session alone verifies the EC2 stopped state.

Release destination clarification is pending (PyPI versus GitHub-only).
Existing v0.3.0 is already published; do not overwrite or retag it. A v* tag
automatically triggers the trusted PyPI publishing workflow after its checks.
No release tag or package publication has been created during closeout.

Release preparation discovered existing CI failures: the BridgeStan integration
lockfile omitted the root crate's smallvec dependency, and a stochastic
cost-weighted-adaptation test assumed monotone step-size effects across different
trajectories. The repair adds the locked dependency and tests the fixed-trace
weighting arithmetic directly, retaining integration checks for changed
adaptation, finite positive steps, equal-cost parity and opt-in defaults.
Production sampler behavior and research accuracy gates are unchanged.
The targeted checks, full all-target/all-feature Rust suite, formatting,
library Clippy and locked BridgeStan check pass on Windows GNU1.88. Cross-platform
CI and package checks are required before publication. Preserve the unrelated
options-flow local edit.
