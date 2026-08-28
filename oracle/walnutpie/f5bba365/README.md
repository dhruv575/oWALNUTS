# Walnutpie parity oracle

These four JSON fixtures are copied unchanged from the MIT-licensed Walnutpie-derived oracle in the production source repository. They were generated from `flatironinstitute/walnutpie` commit `f5bba36529697c34567a2944be36b68e305c546d` and cover the reviewed macro-leaf, span, transition, and transition-sequence parity scenarios.

The fixtures contain exactly 54 scenario units:

- 11 macro-leaf cases in `gaussian_cases.json`;
- 12 span cases in `span_traces.json`;
- 7 transition cases in `transition_traces.json`; and
- 24 transition-sequence units in `transition_sequence_traces.json` (12 transitions in each of two tapes).

Those 54 units have 53 unique scenario names. `nonidentity_diagonal_mass` intentionally appears once in the macro-leaf fixture and once in the span fixture: the same named input validates two different algorithm layers and is counted as two scenario units but one unique name. Each transition in a sequence tape is one scenario unit and has a distinct tape-and-transition identity for unique-name accounting.

The Rust tests consume these fixtures from private, test-only modules; no oracle or prototype API is public.

Run all parity tests without feature flags:

```console
cargo test oracle_tests
```

Run a specific oracle group:

```console
cargo test oracle_tests::macro_leaf
cargo test oracle_tests::span
cargo test oracle_tests::transition
cargo test oracle_tests::sequence
```

`SHA256SUMS.txt` records the exact copied fixture bytes. Original generation used Eigen and the upstream C++ headers; generators and instrumented headers are intentionally excluded because standalone CI validates the pinned outputs rather than regenerating them.

Upstream code and generated oracle provenance are provided under the MIT license; see the repository `NOTICE` and `THIRD_PARTY.md`.