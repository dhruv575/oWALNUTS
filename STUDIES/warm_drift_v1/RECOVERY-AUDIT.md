# WP96 recovery and supplemental audit

Prepared 2026-10-27 before recovery or inspection of the evidence cells. This is
a recovery checklist and a supplemental diagnostic plan, not an amendment to
the frozen study decision. The original `protocol.json`, seed schedule,
accuracy thresholds and failed-cell handling remain authoritative.

## Known state

The local branch froze the study at `9210c9471b2eacc1e1528455720239863bae76f0`.
It contains the harness and analysis but only the remap check and smoke table;
no evidence cells or final results were present when this note was written.
The previous session reported completion of the cells. An archive named
`/home/ubuntu/lanes/warm_drift_v1/wp96-artifacts.tgz` was observed remotely,
but neither that report nor the existence of an archive establishes completeness.

Recover that archive, both lane logs, the remote source commit/status, package
versions and any existing checksums. Verify the archive hash on both ends before
extraction; extract into a separate recovery directory before copying files into
the study. Do not overwrite existing evidence or launch sampling to replace a
finished result. A host-interrupted cell requires a recorded deviation under
`wiki/methods.md`.

## Expected evidence

- 18 cells: two references and 16 warm cells (four policies, two streams, two seeds).
- Each reference: 81 recorded ticks at 0, 25, ..., 2,000. A successful attempt's
  four-chain, 20,000-draw compact file contains 960,000 bytes. A second attempt,
  when required by the frozen gate, is retained separately.
- Each warm cell: 2,001 records, including tick 0; 81 compact draw files if all
  ticks succeed. Tick 0 has four chains and 1,000 draws (48,000 bytes). Later
  saved ticks have 200 draws and the carried chain count, normally four
  (9,600 bytes). Dropped initial chains reduce later file sizes legitimately.
- Every compact file stores three little-endian float32 coordinates per draw:
  `mu`, `log_sigma`, `h_last`, in chain-major order. Original chain identities
  select the shared predictive innovation rows even after an initial chain drop.
- Every completed driver cell should have a `DONE` record. Its exit code alone
  does not establish successful ticks; inspect record statuses and missing ticks.

## Supplemental checks

`audit_recovery.py` reads raw evidence without modifying it. It checks every
planned cell, missing/duplicate/unexpected ticks, completion records, draw-file
sizes, finite values and retained reference-chain identities. It emits an
inventory with byte sizes and SHA256 hashes, including failed reference attempts.

For each selected reference attempt, separately report rank R-hat, bulk ESS and
tail ESS for `mu`, `log_sigma` and `h_last`, retained divergences on kept chains,
and relative quantile MCSE for predictive sigma P50 and P95. Flag R-hat above
1.01 or nonfinite, or either ESS below 400, as supplemental reference concerns.
These flags do not silently replace the frozen gate, which only checks retained
chain count and predictive `h_next` R-hat after adding innovation noise.

Reproduce the original `analyze.py` results using ArviZ 0.23.4 and NumPy 2.5.4.
A local isolated environment has been prepared at
`target/wp96-analysis-env/Scripts/python.exe`. The existing shared environment's
ArviZ 1.3.0 is API-incompatible with the frozen analysis and must not be used.
Record other package versions and do not use laptop timings as sampler evidence.

## Limits on interpretation

The experiment concerns a 250-return sliding-window posterior on two synthetic
streams sharing innovations. It does not test equivalence to a full-history
posterior, broad market regimes, actual executable quotes or profitability.
Accuracy is assessed every 25th tick, including every periodic re-adaptation
tick. This overrepresents immediately re-adapted states relative to their
frequency in the full stream, and does not directly assess the first 24 ticks
after the regime change. Report these limitations even if the frozen rule passes.
Preserving a transition kernel's target does not by itself establish that a
finite warm refresh has reached that target.

No evidence outcome is asserted in this note. Final results belong in the study
README and ledger entry after recovery and verification.
