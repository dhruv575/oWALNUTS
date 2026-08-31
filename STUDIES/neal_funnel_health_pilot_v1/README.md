# Neal funnel health pilot v1

Evidence class: authorized bounded pilot, not confirmation and not a public
benchmark win. The frozen protocol used the centered 10-dimensional Neal
funnel, starts `v=[-3,-1,1,3]`, four sequential chains, 2,000 warmup and
10,000 retained draws per chain, seeds `2026090101`--`2026090103`, target
acceptance `{0.90,0.95}`, refinement levels `{8,12}`, `max_error=0.5`,
divergence threshold 1,000, a one-billion shared callback cap per cell, and a
300-second wall cap per cell.

All 12 compiled preflights started zero callbacks. All 12 authorized cells
completed below both runtime caps. Compilation and preflight were outside the
reported kernel interval.

| seed | accept | refine | seconds | retained calls | div | exhaust | reverse stops | depth | max R-hat | min bulk | min tail | v mean | v var |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026090101 | .90 | 8 | 2.509 | 3,552,033 | 0 | 114 | 4,231 | 211 | 1.0805 | 48.3 | 117.8 | -.377 | 10.874 |
| 2026090101 | .90 | 12 | 2.326 | 3,784,593 | 0 | 0 | 4,490 | 211 | 1.0868 | 32.4 | 206.3 | -.426 | 10.171 |
| 2026090101 | .95 | 8 | 4.831 | 5,197,263 | 0 | 4,828 | 3,509 | 160 | 1.3817 | 9.3 | 4.2 | -2.075 | 22.045 |
| 2026090101 | .95 | 12 | 3.309 | 5,102,010 | 0 | 0 | 4,536 | 168 | 1.1094 | 27.8 | 25.6 | -.807 | 12.507 |
| 2026090102 | .90 | 8 | .805 | 1,689,558 | 0 | 98 | 8,038 | 1 | 1.0874 | 32.2 | 305.3 | -.370 | 9.965 |
| 2026090102 | .90 | 12 | .857 | 1,955,147 | 0 | 0 | 8,104 | 1 | 1.0678 | 48.6 | 197.6 | -.240 | 10.342 |
| 2026090102 | .95 | 8 | 1.313 | 3,272,831 | 0 | 122 | 7,281 | 43 | 1.0254 | 95.6 | 163.4 | -1.288 | 15.309 |
| 2026090102 | .95 | 12 | 3.016 | 2,523,755 | 0 | 0 | 6,826 | 3 | 1.0247 | 143.4 | 339.2 | -.712 | 12.470 |
| 2026090103 | .90 | 8 | 2.110 | 2,831,846 | 0 | 121 | 6,435 | 20 | 1.0949 | 38.2 | 232.7 | -1.034 | 11.755 |
| 2026090103 | .90 | 12 | 1.420 | 3,412,570 | 0 | 0 | 6,357 | 20 | 1.0720 | 45.5 | 147.8 | -.758 | 12.151 |
| 2026090103 | .95 | 8 | 1.841 | 2,057,839 | 0 | 27 | 5,402 | 24 | 1.0385 | 149.3 | 185.8 | -.394 | 9.992 |
| 2026090103 | .95 | 12 | 1.361 | 2,545,167 | 0 | 0 | 5,825 | 18 | 1.0603 | 101.6 | 135.4 | -.757 | 11.791 |

Decision: **no selection**. No grid setting passed the rank R-hat, bulk ESS,
and tail ESS gates on all three seeds; level 8 also had refinement
exhaustions in every cell. The frozen moment gates additionally omitted an
interval construction and therefore cannot be assigned post hoc.

The initial `artifacts/results` run is retained as invalidated diagnostic
evidence: it revealed that divergence telemetry incorrectly included discarded
coarse refinement probes. The corrected kernel counts only accepted
trajectories (and fail-closed invalid/exhausted trajectories);
`artifacts/results-corrected` is the decision-bearing result.

Key hashes:

- protocol: `6f32e4b3f5683cca602369cbb6f60cf0ab8d0795db1e91cb445b7aebb0b562b0`
- corrected kernel: `7e7305c0b6c38cb1b3691fd8802f2a352aec5af0ed009f821be18e6ee97785b9`
- runner: `c8b884c3ffe8de16c8614678b84e2d07ff535d03b61cfc82678f334f8c92c3ca`
- preflight: `242cc4bdad9e34d01fa36dea7ef4d69cda8ffcb1b9423f6333798d643066f938`
- corrected summary: `7049a5a843fde48ea6bf3ca04c391c84684b59b99111763e99ef123b487d3d39`

No confirmation run is authorized. A new preregistration is required; the
frozen confirmation settings cannot be chosen because the pilot selection
condition failed.
