# Neal funnel intervention pilot v2

Evidence class: authorized mechanism-and-feasibility pilot; not confirmation
and not a benchmark claim. One checksum-bound attempt completed all 12 frozen
cells without callback, wall, or partial-output failures. Compilation and
preflight were outside cell timing.

| cell | seed | start | policy | sec | calls | div/exhaust/depth | reverse | max R-hat | scale bulk/tail | mean/var | eligible |
|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 0 | 2026091101 | dispersed | baseline | 1.489 | 2,489,300 | 0/0/81 | 2,928 | 1.0230 | 108.3/83.6 | -.190/8.653 | no |
| 1 | 2026091101 | dispersed | robust | 2.765 | 3,766,889 | 0/0/244 | 5,009 | 1.0333 | 185.1/194.3 | -.065/9.399 | no |
| 2 | 2026091101 | zero | baseline | 3.026 | 4,960,258 | 0/0/505 | 4,251 | 1.0269 | 95.9/190.3 | -.285/9.718 | no |
| 3 | 2026091101 | zero | robust | 3.180 | 6,072,429 | 0/0/583 | 4,624 | 1.0657 | 67.3/41.2 | -.389/11.206 | no |
| 4 | 2026091102 | dispersed | baseline | 1.974 | 3,510,465 | 0/0/147 | 4,543 | 1.0329 | 178.1/151.2 | -.224/11.191 | no |
| 5 | 2026091102 | dispersed | robust | 1.818 | 2,109,833 | 0/0/18 | 4,586 | 1.0326 | 96.1/135.9 | -.333/8.367 | no |
| 6 | 2026091102 | zero | baseline | 3.032 | 3,018,407 | 0/0/156 | 5,812 | 1.0221 | 111.7/252.8 | -.497/10.883 | no |
| 7 | 2026091102 | zero | robust | 2.458 | 4,188,015 | 0/0/93 | 6,917 | 1.0625 | 72.2/140.8 | -.854/11.834 | no |
| 8 | 2026091103 | dispersed | baseline | 2.945 | 3,466,027 | 0/0/128 | 4,255 | 1.0308 | 90.8/52.5 | -.204/11.410 | no |
| 9 | 2026091103 | dispersed | robust | 5.226 | 3,720,131 | 0/0/16 | 4,725 | 1.1105 | 27.4/82.4 | -.884/12.239 | no |
| 10 | 2026091103 | zero | baseline | 2.908 | 2,105,983 | 0/0/27 | 6,829 | 1.0116 | 212.9/319.6 | -.541/11.075 | yes |
| 11 | 2026091103 | zero | robust | 5.744 | 2,866,158 | 0/0/101 | 5,539 | 1.0531 | 92.4/161.9 | -.383/10.391 | no |

All cells had zero corrected divergences, refinement exhaustions, invalid
stops, and recoverable failures. The robust dispersed-start ESS/call ratios
relative to baseline were `1.1301`, `0.8978`, and `0.2808`; median `0.8978`.
Robust zero/dispersed start-sensitivity ratios were `0.2254`, `0.3785`, and
`4.3821`, all outside the required `[0.67,1.5]` interval. Robust cells also
failed the all-cell eligibility and step-dispersion requirements.

Decision: **no selection**. Longer warmup plus initial-step search is falsified
as the preregistered general-purpose intervention. Cell 10 passing alone is
descriptive baseline evidence and cannot select a start or policy.
Confirmation remains unauthorized.

Hashes:

- protocol: `a9c7657491f445f57766d90002bd97eb7dd3d13e1dbca7e1a8e44ec53a8f49c3`
- authorization: `0aed6a18989e8d94314d0eb96696ffa649d29b93f6f21fc2c7bd3273b09da7fa`
- summary: `a1ac80da0d543a5a7602d89defa27bb2439d9accef61c7be017a53becad18839`

Every raw cell hash is recorded in `CHECKSUMS.sha256`.
