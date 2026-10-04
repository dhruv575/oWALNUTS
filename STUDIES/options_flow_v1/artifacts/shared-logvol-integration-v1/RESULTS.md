# Optional likelihood integration correctness

The initial focused suite passed 8 tests in 45.03 seconds. It explicitly checked the imported adapter and extension paths and hashes against the intended attested runtime before compiling the T1000 target. The existing public-worker regression suite passed 6 tests in 14.80 seconds, and mixed-coordinate regressions passed 6 tests in 8.29 seconds.

The final focused suite passed 8 tests in 18.47 seconds after making its T1000 fixture and saved-position inputs portable: they now use committed relative archive paths rather than ignored target files or absolute development-machine paths. The initial exact-runtime assertion remains preserved in the initial test snapshot and validation evidence; the portable final test does not independently enforce an absolute runtime location. Both runs used the selected package environment recorded in the evidence. The existing PyTensor Scan deprecation warning was non-fatal.

Tests cover normalized automatic-gradient parity for T1/G1, T7/G4 and saved T1000 positions, unsupported recipe and mask rejection, and a tiny actual worker invocation. That invocation completed with canonical draws shaped 4 ? 8 ? 9, retained canonical starts, and the candidate variant recorded in top-level, settings and compilation metadata. Its expected failed precision screen and exit code 1 were asserted; this short correctness run is not evidence of sampling adequacy.

The optional shared-log-volatility expression leaves baseline defaults and baseline record schema unchanged. These results make no speed, calibration, numerical-domain completeness or market-usefulness claim. A separate attested integrated 18-case extreme-boundary check is pending. Existing shared extreme-domain limitations remain explicitly unresolved until that evidence is reviewed.

Initial and final source/test snapshots and validation summaries are preserved. origin-inventory.json identifies copied files and hashes; CHECKSUMS.sha256 covers the complete archive, excluding the checksum file itself.
