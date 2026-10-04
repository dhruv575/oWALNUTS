# Corrected runtime experiment

Version 3 remains a failed provenance experiment: both processes imported the main editable package rather than the configured attested worktree package. Its outcomes, 17.779-second cost, actual runtime bytes, and failed independent audit remain archived in commit e50f5ca. This correction does not replace that experiment.

Version 4 retains the same two compilation orders, identical five saved positions, four stress regimes, six alternating paired blocks per process, 1,500 calls per block, CPU0, 600-second per-process timeout, and 8 GiB memory limit. It performs no sampling. Timing and inference limitations from BENCHMARK_PLAN.md still apply.

The launcher explicitly selects the worktree package through PYTHONPATH and disables the user site. Before compilation and after timing, the worker checks the resolved paths and SHA256 values of the imported adapter and native extension against the explicit runtime identity and bound inputs. The import-only preflight passed. Five runtime guard tests, including wrong-path and wrong-hash rejection, passed twice after making test artifacts temporary.

Frozen configuration: benchmark-config-v4.json, SHA256 4dd12ed6d6b3ed9c0d2c5b33aaaadff860b43349f2795ec16858e9a17ca54d28. Root independently checked all 193 bound files before execution.

Command, after the runtime guard review and quiet-window clearance:

`target/python-workflow-env/Scripts/python.exe target/mixed-target-optimization-v1/launch_benchmark_v4.py --config target/mixed-target-optimization-v1/benchmark-config-v4.json --out target/mixed-target-optimization-v1/benchmark-run-v4`

Use the new exclusive output directory once. Preserve every outcome and all costs. Recompute every timing block and independently verify actual imported runtime identities before accepting the corrected comparison. Prior boundary observations are not an attested-runtime robustness qualification; that limitation remains open for integration validation.
