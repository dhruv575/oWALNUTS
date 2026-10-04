# Shared validation for reporting

`production_calibration_adapter.normalize_shared` is an explicit opt-in reporting API using `cohort-content-prepost-v1`. Existing `normalize` and the feasibility controller retain their legacy behavior. This change launches no sampling and changes no statistical thresholds.

Callers provide the frozen expected source inventory and a function that enumerates the current inventory. Every expected source must have a content hash in the shared bindings; additional bound runtime and evidence files are allowed. Empty inventories, empty bindings, conflicting hashes, and inventory drift fail validation.

The transaction hashes shared files before processing and after all records have been processed. Each fit retains its existing artifact, identity, diagnostic, interval, and cost checks. A shared validation failure invalidates every intended record; a local normalization failure remains local. Known invocation costs remain available. Invalid manifests and duplicate intended IDs are rejected before transaction admission.

Only the completed transaction result is suitable for publication. Direct use of the adapter's shared-context seam produces provisional records marked `shared_validation_provisional`, with `usable=False` and `provenance_valid=False`. The transaction restores the validated flags only after its final shared check succeeds; shared failure leaves every record invalid. Callers must not publish provisional records. A passed shared check does not imply that every individual record is usable. Results remain `qualified=False`.

Pre/post checking changes the temporal observation boundaries compared with per-fit checks. It does not provide continuous monitoring and cannot detect every transient modification restored before the final check. No file-size or modification-time cache substitutes for content hashing.

Historical experiment manifests and timings remain unchanged. Replay with a new reporter must be labeled as an alternate analysis, verify original worker source identities against preserved bytes, and separately bind the new reporter. The original resource screen's 2,157.532 seconds of reporting remains its recorded cost.

Validation includes mutation, frozen inventory, conflicting bindings, malformed return identities, failure-cost preservation, and mock legacy-record equivalence tests. The focused regression suite passes 71 tests and three subtests. The completed saved-output replay reproduced all 40 original successful records exactly; an independent audit passed 755 checks. Failure-case behavior is covered by tests, not by this all-successful replay.

The alternate replay took 611.155 seconds internally (611.333 seconds in its wrapper), including 572.073 seconds for the normalization transaction. This is a posthoc comparison with the original 2,157.532-second reporting run: it adds full raw-artifact pre/post hashing and archive resolution, but omits coverage-summary generation. It does not establish an isolated normalization speed ratio or a sampler speedup. The earlier failed replay and its 74.105-second wrapper cost are also preserved. See [archived evidence](artifacts/report-provenance-optimization-v1/RESULTS.md).
