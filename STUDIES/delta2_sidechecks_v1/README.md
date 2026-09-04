# delta2_sidechecks_v1 (WP37A)

Status: **preregistration scaffold frozen before harness, implementation,
build, or sampling**.

This study is a qualification gate for a possible later adaptive-delta study.
It compares only fixed `delta = 1` and fixed `delta = 2` on fresh pure-Rust
funnel, strict noncentered Eight Schools, and analytic 100-D Gaussian cells.
It cannot select fixed 2 as a default.

Planned evidence: 84 one-shot child cells using seeds 93101–93112 (strict
Eight Schools uses 93101–93106 with three bit-identical repetitions). No cell
has been implemented or run.

The frozen decision is conjunctive: only a pass of every funnel, Eight
Schools, Gaussian, completeness, identity, and provenance gate permits a
separately preregistered adaptive-delta implementation study. Any failure or
inconclusive gate rejects fixed 2 and adaptive-to-2 and moves the research
program to the cheaper reverse-coarsening check.

Protocol details are in `PREREGISTRATION.md` and `protocol.json`.
Protocol-review clarifications are frozen append-only in `AMENDMENT-1.md`;
it controls where more specific, while the original two frozen files and
their checksums remain unchanged.

## Scaffold checksums

SHA-256 over UTF-8 bytes with line endings normalized to LF:

- `PREREGISTRATION.md`:
  `4f61248d8207e0b3fc84f9d55e3a093b8fb963e1c6d1ba0e88ee1669a2aecf73`
- `protocol.json`:
  `bf82f4a075c2811666b845cb90e763a94a7eb76c979d956377913be2dc9ce58b`
