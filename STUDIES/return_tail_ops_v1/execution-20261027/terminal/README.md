# Completed stored-draw arithmetic: operational audit

All 27 fixed jobs exited successfully and drained: 12 candidate shards, 12 reference shards, and three monthly reports. The fixed 4,368 candidate origins, 24 reference origins, and 13,104 arm-origin slots were accounted for. All 34 sealed source files and 89 copied metadata files matched their archive identities. The production authorization was a status-only change from the pending manifest.

The aggregate envelope completed in 241.7566 seconds, with peak RSS 6,083,375,104 bytes and 56,927,373 output bytes, below the 3,720-second / 8 GiB / 1 GiB limits. Candidate worker walls were 210.332 to 210.844 seconds; reference workers 15.991 to 16.383 seconds; reports 3.646 to 3.653 seconds. These timings include process startup, verification and persistence, not just quantile arithmetic. Maximum individual worker RSS was 605,884,416 bytes, below 1 GiB.

| Phase | Samples | Weighted average CPU / 12 reserved cores | Maximum sampled CPU / 12 cores |
| --- | ---: | ---: | ---: |
| Candidate | 41 | 101.37% | 104.08% |
| Reference | 4 | 80.46% | 105.43% |
| Report | 2 | 0.86% | 1.39% |

These are sampled CPU-time deltas for all owned live processes, including batch orchestration and nested monitors; they are not the utilization of only twelve arithmetic workers. Consequently the normalized value can exceed 100%. First sightings and processes exiting between samples omit CPU, and a boundary interval is assigned to its ending phase. Reporting is brief and largely serial. No additional work was launched merely to fill cores.

AUDIT.json records the checks and per-worker timings. Exact metadata is preserved here; COPIED-CHECKSUMS.sha256 binds the copies. Parent verified all 9,256 files in the full archive, SHA-256 94434e4fe6abb30e1f66c699fbee9c250a3888bbe39b9dd31d11fdf09cd0e5d6 (8,077,968 bytes). Full raw evidence remains under C:/dev/owalnuts/target/return-tail-verified-20261027/return-tail-20261027, with the parent-retained archive. No statistical scoring, sampling or bootstrap was rerun for this audit. Scientific interpretation belongs to the separate predictive risk-limit report.

AWS remains running under the user's preference and parent lifecycle control. This audit issued no lifecycle commands.
