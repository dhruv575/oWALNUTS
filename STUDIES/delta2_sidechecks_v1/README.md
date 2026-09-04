# delta2_sidechecks_v1 (WP37A)

Status: **complete — `FIXED2_NOT_QUALIFIED_FOR_ADAPTIVE_TO_2`**.

This preregistered qualification gate compared only explicit fixed
`max_error = 1` and fixed `max_error = 2` on fresh pure-Rust funnel, strict
noncentered Eight Schools, and analytic 100-D Gaussian cells. All 84 canonical
children were launched exactly once, in manifest order, with process-valid,
schema-valid, configuration-authenticated results. No sampler default,
production code, seed, setting, or frozen protocol file changed.

The result rejects the preregistered adaptive-to-2 path. Fixed 2 remains
ineligible for default selection. The next registered work is the cheaper
reverse-coarsening check.

## Result

| gate | result |
|---|---|
| F1 | PASS |
| F2 | PASS |
| F3 | **FAIL** |
| F4 | **FAIL** |
| F5 | PASS |
| E1 | PASS |
| E2 | PASS |
| E3 | PASS |
| E4 | PASS |
| G1 | PASS |
| G2 | PASS |
| G3 | PASS |
| G4 | PASS |

Funnel pooled accuracy passed: fixed1/fixed2 respectively estimated
`P(omega < -5)` as 0.046642/0.046468,
`P(omega < -6)` as 0.022892/0.022133, and variance as 8.924742/8.903268.
F3 failed because fixed2 had retained divergences on seeds 93102, 93105,
93107, 93108, 93109, and 93111 (3, 2, 1, 4, 1, and 2); only 6/12 fixed2
seeds were gross-safe. F4 failed because only 2/12 fixed2 seeds were healthy,
below the frozen minimum of 9 (fixed1 was also 2/12). F5 still passed:
fixed2 versus fixed1 totals were 13 versus 14 divergences, 0 versus 0 invalid
stops, and 70 versus 276 refinement exhaustions.

All strict Eight Schools triplicates were byte-identical. Every amended E2
functional passed; the fixed2/fixed1 geometric-mean minimum bulk
ESS/callback ratio was 1.047787, and both arms were healthy on 6/6 seeds.
All 100 pooled Gaussian coordinate checks passed; its ratio of seed-median
mean bulk ESS/retained-call scores was 1.016804, and both arms were healthy
on 12/12 seeds.

Predictions P1–P3 held; P4, the predicted qualification label, did not.
The 84 children used 30.045 seconds summed process time and spanned 38.884
seconds from first to last launch marker.

## Provenance and artifacts

- harness source commit: `e91458dca1aa7944b07c65514ad2313b4a60cd4d`
- committed pre-evidence provenance: `6b556f0`
- canonical manifest SHA-256:
  `7ed4837570692ce2c7f44939d0e32b276b14eb834d86b4869d3de44149138c86`
- bound GNU Rust 1.88 release binary SHA-256:
  `d1a6c05083a00660dd2a15f314321b5e7678685bd85f262fc1ac18713662749c`
- analysis: Python 3.11.16, ArviZ 0.23.4, NumPy 2.4.6

`artifacts/launches`, `processes`, `stdout`, `stderr`, and `raw` archive every
planned outcome. `artifacts/cells`, `summary.json`, `gate-table.md`,
`results-table.md`, and `verdict.md` contain the authenticated analysis.
`CHECKSUMS.sha256` is the final file inventory.

Protocol details remain frozen in `PREREGISTRATION.md`, `protocol.json`, and
the controlling clarification `AMENDMENT-1.md`. Their UTF-8/LF-normalized
SHA-256 values are:

- `PREREGISTRATION.md`:
  `4f61248d8207e0b3fc84f9d55e3a093b8fb963e1c6d1ba0e88ee1669a2aecf73`
- `protocol.json`:
  `bf82f4a075c2811666b845cb90e763a94a7eb76c979d956377913be2dc9ce58b`
- `AMENDMENT-1.md`:
  `2990becb882452275c7eee6c1b9305d117a79dddfae41bd77473b79476c9d48f`
