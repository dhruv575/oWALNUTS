# Harness calibration (non-evidence; run before the preregistration was frozen)

Seeds 40000001–40081040, disjoint from the evidence matrix and not reused.
Run from Git Bash with the same PATH as the evidence run. Counts of nonzero
exits / `0xC0000374`:

| configuration | children | faults | heap |
|---|---:|---:|---:|
| micro `workers_resident` (first harness version, 1 model, serialized, 128 threads/child) | 40 | 0 | 0 |
| micro `concurrent_resident` 4 replicas, synchronized rounds | 40 | 0 | 0 |
| micro `concurrent_resident` 4 replicas, staggered spawn, 256 threads/child | 30 | 0 | 0 |
| `sampler_concurrent` sblrc 4r/4c, 100 warmup/100 draws | 25 | 0 | 0 |
| `sampler_concurrent` sblrc 4r/4c, 4/4 (comparator shape) | 80 | 0 | 0 |
| `sampler_concurrent` sblrc 8r/8c, 20/20 | 40 | 0 | 0 |
| `sampler_concurrent` arK 4r/4c, 50/50 | 40 | 0 | 0 |

One earlier batch of 40 children exited with code 1 because the calibration
command passed the wrong number of arguments (a usage error, not a native
fault). It is excluded above. Calibration informed only the child counts and
shape; the evidence matrix in `protocol.json` was frozen and committed
(`c4f3fcbb`) before any evidence child ran.
