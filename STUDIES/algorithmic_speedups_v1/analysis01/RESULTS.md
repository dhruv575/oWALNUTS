# Algorithmic speedup pilot results

Exploratory two-seed pilots; no qualified independent spatial reference; no general 10x claim

| Campaign / method | Passing runs | Median sampling seconds | Median full seconds | Worst R-hat | Minimum bulk ESS |
|---|---:|---:|---:|---:|---:|
| physics_repair01 / da_affine | 0/2 | 0.465 | 3.335 | 1.047 | 73.4 |
| physics_repair01 / da_transport | 2/2 | 0.610 | 3.411 | 1.001 | 5661.0 |
| physics_repair01 / mh_affine | 0/2 | 0.487 | 3.330 | 1.011 | 315.8 |
| physics_repair01 / mh_transport | 2/2 | 0.658 | 3.441 | 1.000 | 12670.8 |
| physics_repair01 / nuts_affine | 0/2 | 0.358 | 2.447 | 1.005 | 511.8 |
| physics_repair01 / nuts_raw | 0/2 | 0.630 | 2.712 | 1.009 | 715.0 |
| physics_repair01 / nuts_transport | 2/2 | 0.271 | 2.431 | 1.001 | 2164.5 |
| physics_repair01 / walnuts_affine | 0/2 | 0.459 | 2.581 | 1.004 | 457.6 |
| physics_repair01 / walnuts_raw | 0/2 | 0.841 | 2.963 | 1.006 | 671.3 |
| physics_repair01 / walnuts_transport | 2/2 | 0.331 | 2.502 | 1.003 | 1692.8 |
| physics_precision01 / nuts_affine | 2/2 | 0.986 | 3.516 | 1.002 | 1925.8 |
| physics_precision01 / nuts_raw | 2/2 | 1.816 | 4.356 | 1.001 | 3317.7 |
| physics_precision01 / nuts_transport | 2/2 | 0.745 | 3.300 | 1.001 | 8320.2 |
| physics_precision01 / walnuts_affine | 2/2 | 1.357 | 3.885 | 1.001 | 2005.5 |
| physics_precision01 / walnuts_raw | 2/2 | 2.272 | 4.780 | 1.003 | 2627.4 |
| physics_precision01 / walnuts_transport | 2/2 | 0.981 | 3.550 | 1.000 | 7144.7 |
| results / blocked_dense | 0/2 | 46.094 | 85.643 | 2.416 | 4.9 |
| results / blocked_grid1 | 0/2 | 3.682 | 12.773 | 2.416 | 4.9 |
| results / blocked_grid4 | 0/2 | 8.242 | 17.207 | 2.604 | 4.8 |
| results / nuts | 0/2 | — | — | — | — |
| repair01 / nuts | 1/2 | 647.783 | 654.704 | 1.002 | 1043.5 |
| grid_native01 / nuts_grid | 2/2 | 17.727 | 22.396 | 1.002 | 2272.2 |
| grid_native_early01 / nuts_grid | 1/1 | 18.149 | 22.818 | 1.002 | 2304.2 |
| grid_precision01 / nuts_grid | 1/1 | 28.079 | 35.958 | 1.001 | 4606.2 |

Failed or capped jobs: 4. See SUMMARY.json and original logs.

Passing physics rows satisfy convergence, reference agreement and MCSE gates. Passing spatial rows satisfy only exploratory convergence gates; they do not establish posterior fidelity against a qualified independent reference. Full cost includes imports, diagnostics and, for transported physics, training plus shared preparation. Compilation is reported separately and is not included in worker times.
