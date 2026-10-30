# Kernel overhead screening

Source baseline: da42c8fb. Build the existing kernel_bench example in release
mode, locked dependencies, no research features. Three fixed existing workloads
are exposed mechanism probes, not fresh posterior validation. Run five separate
processes with --repeat 1, pinned to core 0, timeout 120 seconds per process.
Preserve every output and exit code; summarize medians, never best-of-five.
The instrument counts heap allocations and target calls and fingerprints draws.
Its separately timed target probe is only an approximate overhead estimate.

No kernel change is selected by this baseline alone. If a candidate follows,
require paired alternated-order runs, exact fingerprints and work counts,
oracle tests and subsequent fresh-seed posterior checks for any semantic change.
Avoiding unused reverse-schedule allocation is a candidate only if the measured
benefit warrants it; a small runtime optimization does not meet the goal.

Local build attempt failed because link.exe is unavailable. Preserve this as an
environment failure. Remote build uses /dev/shm/kernel-profile-20261029 to avoid
disk pressure: maximum four compile workers, timeout 300 seconds. Preserve
source hash, compiler version, build log, executable hash and benchmark results.
No active inference dependencies are modified.
