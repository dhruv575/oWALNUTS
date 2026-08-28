# Security and support scope

## Reporting

Report suspected vulnerabilities privately to the repository maintainers. Do not include sensitive exploit details in a public issue before maintainers have responded.

## Supported scope

Only the latest unreleased revision is supported, and only for the documented fixed-diagonal internal-beta facade on supported Rust toolchains. This project does not claim validation for hostile in-process target callbacks, heavy-tailed or constrained targets, hierarchical models, or general production inference.

Cancellation and deadlines are cooperative. A callback that blocks, deadlocks, or aborts the process cannot be interrupted safely; isolate untrusted target code in a killable process. Resource limits account for documented crate allocations, not total process memory.
