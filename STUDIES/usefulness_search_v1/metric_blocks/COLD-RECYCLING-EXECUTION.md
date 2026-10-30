# Execution audit

Build01 failed before sampling because the generated Rust driver used `.9`, which Rust requires to be written `0.9`. Failed source/logs are preserved; repair_cold_literal.py makes only that correction.

Build02 compiled but the inherited coordinate unit test failed: it expected enabled observation immediately after reset. The new retained-only observer deliberately starts outside the retained phase. repair_cold_phase_test.py preserves failed source and built binary, asserts that features are empty before entering the phase, then explicitly enters retained phase before testing the existing dense-coordinate restoration identity. No sampling code or statistical gate changed in that repair. Build03 passed eight tests for each driver.

The phase hook brackets the existing kernel dispatch in ChainRunner::advance, uses its actual transition_index >= discarded predicate, and resets false immediately after the call, before subsequent adaptation/error handling. Auxiliary searches outside that dispatch and warmup transitions therefore do not contribute observables. Runtime checks must still establish exactly one record per retained draw and exact metadata/work parity. This patch supports the tested sequential identity/diagonal path only; the global observer is not a concurrent production API.
