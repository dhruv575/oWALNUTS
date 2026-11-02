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
18.223.111.36. The expired CLI profile was refreshed through the approved
AWS login. The restricted instance archive role was not broadened.
AWS login was explicitly approved and completed. EC2 StopInstances was issued,
the instance-stopped waiter completed, and DescribeInstances confirmed stopped
at2026-11-02T08:17:16Z. See AWS-SHUTDOWN-20261102.json. No instance termination,
EBS deletion or new experiments occurred.

Dhruv explicitly authorized GitHub and PyPI publication. Version 0.4.0 is now
published on both services from commit d83226da95c6b935cd26c4c787a91eecde9c3ee8.
All nine core CI jobs, five platform wheels, source-distribution installation,
and full optional-backend suites on Python 3.10 and 3.13 passed. All six PyPI
files match the tested CI artifacts by SHA256, and a fresh PyPI installation
passed a sampling smoke test. GitHub carries the same six release files.
See RELEASE-v0.4.0-PUBLISHED.json and RELEASE-v0.4.0-PYPI-SMOKE.json.
The two unsuccessful prepublication attempts are preserved in
RELEASE-v0.4.0-ATTEMPTS.json. Existing published v0.3.0 remains untouched.
The release workflow requires successful core CI for the exact commit.

All eight archives were uploaded to the private S3 research bucket using the
refreshed local profile, downloaded by exact VersionId, and SHA256-verified.
See FUNNEL-CLOSEOUT-S3-VERIFIED.json. An earlier attempt using the restricted
instance role was denied; no IAM permissions were broadened. Local originals,
restored copies and the existing EBS evidence are retained.

Release preparation discovered existing CI failures: the BridgeStan integration
lockfile omitted the root crate's smallvec dependency, and a stochastic
cost-weighted-adaptation test assumed monotone step-size effects across different
trajectories. The repair adds the locked dependency and tests the fixed-trace
weighting arithmetic directly, retaining integration checks for changed
adaptation, finite positive steps, equal-cost parity and opt-in defaults.
Production sampler behavior and research accuracy gates are unchanged.
The targeted checks, full all-target/all-feature Rust suite, formatting,
library Clippy and locked BridgeStan check pass on Windows GNU1.88. Cross-platform
CI and package checks subsequently passed before publication. The unrelated
options-flow local edit is preserved.
