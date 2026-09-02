# kernel_efficiency_v1 results (seed medians over 3 seeds, 4 chains x 1000 warmup / 1000 draws)

## eight-schools (10-D)

| arm | min bulk ESS/grad x1e3 | vs NUTS | with cache x1e3 | vs NUTS | ESS(x^2)/grad x1e3 | grad/transition | leaves/transition | non-leaf grad/tr | depth | refined | stops |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| nuts-ref | 73.49 | 1.00x | 73.49 | 1.00x | 59.59 | 8.1 | 8.1 | 0.00 | 3.06 | 0.000 | uturn 1.000, divergent 0.001 |
| default | 59.16 | 0.81x | 66.56 | 0.91x | 50.85 | 9.0 | 7.3 | 1.71 | 3.00 | 0.059 | outer_uturn 0.794, recursive_uturn 0.097, reverse_coarser 0.110 |
| default+cache | 66.55 | 0.91x | 66.56 | 0.91x | 57.68 | 8.0 | 7.3 | 0.71 | 3.00 | 0.059 | outer_uturn 0.794, recursive_uturn 0.097, reverse_coarser 0.110 |
| delta1000 | 61.93 | 0.84x | 69.98 | 0.95x | 56.18 | 8.7 | 7.7 | 1.00 | 3.06 | 0.000 | outer_uturn 0.882, recursive_uturn 0.118, reverse_coarser 0.000 |
| exhaust-accept | 59.16 | 0.81x | 66.56 | 0.91x | 50.85 | 9.0 | 7.3 | 1.71 | 3.00 | 0.059 | outer_uturn 0.794, recursive_uturn 0.097, reverse_coarser 0.110 |
| cross | 54.48 | 0.74x | 61.31 | 0.83x | 51.87 | 8.9 | 7.3 | 1.68 | 3.00 | 0.061 | outer_uturn 0.798, recursive_uturn 0.101, reverse_coarser 0.101 |
| rhosum | 56.46 | 0.77x | 63.48 | 0.86x | 50.23 | 9.4 | 7.7 | 1.72 | 3.07 | 0.057 | outer_uturn 0.822, recursive_uturn 0.067, reverse_coarser 0.112 |
| exhaust-accept+rhosum | 56.46 | 0.77x | 63.48 | 0.86x | 50.23 | 9.4 | 7.7 | 1.72 | 3.07 | 0.057 | outer_uturn 0.822, recursive_uturn 0.067, reverse_coarser 0.112 |
| levels1-accept | 61.93 | 0.84x | 69.98 | 0.95x | 56.18 | 8.7 | 7.7 | 1.00 | 3.06 | 0.000 | outer_uturn 0.882, recursive_uturn 0.118, refinement_exhausted 0.000 |
| levels1-accept+rhosum | 66.51 | 0.91x | 74.66 | 1.02x | 52.69 | 9.2 | 8.2 | 1.00 | 3.13 | 0.000 | outer_uturn 0.913, recursive_uturn 0.087, refinement_exhausted 0.000 |
| rhosum+cache | 63.47 | 0.86x | 63.48 | 0.86x | 56.20 | 8.4 | 7.7 | 0.72 | 3.07 | 0.057 | outer_uturn 0.822, recursive_uturn 0.067, reverse_coarser 0.112 |
| exhaust-accept+rhosum+cache | 63.47 | 0.86x | 63.48 | 0.86x | 56.20 | 8.4 | 7.7 | 0.72 | 3.07 | 0.057 | outer_uturn 0.822, recursive_uturn 0.067, reverse_coarser 0.112 |

Per-seed min bulk ESS/grad x1e3: nuts-ref: 73.49/79.17/64.71, default: 50.72/60.08/59.16, rhosum: 54.22/56.46/56.96, exhaust-accept+rhosum: 54.22/56.46/56.96, levels1-accept+rhosum: 66.51/76.39/56.57

## gaussian-100 (100-D)

| arm | min bulk ESS/grad x1e3 | vs NUTS | with cache x1e3 | vs NUTS | ESS(x^2)/grad x1e3 | grad/transition | leaves/transition | non-leaf grad/tr | depth | refined | stops |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| nuts-ref | 115.63 | 1.00x | 115.63 | 1.00x | 41.74 | 8.3 | 8.3 | 0.00 | 3.13 | 0.000 | uturn 1.000 |
| default | 86.26 | 0.75x | 93.58 | 0.81x | 32.37 | 12.8 | 11.8 | 1.00 | 3.33 | 0.000 | outer_uturn 0.860, recursive_uturn 0.140, reverse_coarser 0.000 |
| default+cache | 93.57 | 0.81x | 93.58 | 0.81x | 35.12 | 11.8 | 11.8 | 0.00 | 3.33 | 0.000 | outer_uturn 0.860, recursive_uturn 0.140, reverse_coarser 0.000 |
| delta1000 | 86.26 | 0.75x | 93.58 | 0.81x | 32.15 | 12.8 | 11.8 | 1.00 | 3.33 | 0.000 | outer_uturn 0.861, recursive_uturn 0.140 |
| exhaust-accept | 86.26 | 0.75x | 93.58 | 0.81x | 32.37 | 12.8 | 11.8 | 1.00 | 3.33 | 0.000 | outer_uturn 0.860, recursive_uturn 0.140, reverse_coarser 0.000 |
| cross | 112.63 | 0.97x | 126.70 | 1.10x | 45.18 | 9.3 | 8.3 | 1.00 | 3.16 | 0.000 | outer_uturn 0.922, recursive_uturn 0.078, reverse_coarser 0.000 |
| rhosum | 112.65 | 0.97x | 126.35 | 1.09x | 34.99 | 9.4 | 8.4 | 1.00 | 3.17 | 0.000 | outer_uturn 0.917, recursive_uturn 0.083, reverse_coarser 0.000 |
| exhaust-accept+rhosum | 112.65 | 0.97x | 126.35 | 1.09x | 34.99 | 9.4 | 8.4 | 1.00 | 3.17 | 0.000 | outer_uturn 0.917, recursive_uturn 0.083, reverse_coarser 0.000 |
| levels1-accept | 86.26 | 0.75x | 93.58 | 0.81x | 32.15 | 12.8 | 11.8 | 1.00 | 3.33 | 0.000 | outer_uturn 0.861, recursive_uturn 0.140 |
| levels1-accept+rhosum | 115.43 | 1.00x | 129.47 | 1.12x | 35.71 | 9.4 | 8.4 | 1.00 | 3.17 | 0.000 | outer_uturn 0.917, recursive_uturn 0.083 |
| rhosum+cache | 126.33 | 1.09x | 126.35 | 1.09x | 39.14 | 8.4 | 8.4 | 0.00 | 3.17 | 0.000 | outer_uturn 0.917, recursive_uturn 0.083, reverse_coarser 0.000 |
| exhaust-accept+rhosum+cache | 126.33 | 1.09x | 126.35 | 1.09x | 39.14 | 8.4 | 8.4 | 0.00 | 3.17 | 0.000 | outer_uturn 0.917, recursive_uturn 0.083, reverse_coarser 0.000 |

Per-seed min bulk ESS/grad x1e3: nuts-ref: 115.63/131.40/110.02, default: 108.60/83.49/86.26, rhosum: 112.65/122.37/101.39, exhaust-accept+rhosum: 112.65/122.37/101.39, levels1-accept+rhosum: 115.43/122.49/101.39

## corr-gaussian-50 (50-D)

| arm | min bulk ESS/grad x1e3 | vs NUTS | with cache x1e3 | vs NUTS | ESS(x^2)/grad x1e3 | grad/transition | leaves/transition | non-leaf grad/tr | depth | refined | stops |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| nuts-ref | 22.50 | 1.00x | 22.50 | 1.00x | 16.86 | 33.8 | 33.8 | 0.00 | 4.95 | 0.000 | uturn 1.000 |
| default | 23.12 | 1.03x | 23.87 | 1.06x | 17.31 | 31.8 | 30.6 | 1.12 | 4.94 | 0.011 | outer_uturn 0.874, recursive_uturn 0.105, reverse_coarser 0.014 |
| default+cache | 23.87 | 1.06x | 23.87 | 1.06x | 17.85 | 30.8 | 30.6 | 0.13 | 4.94 | 0.011 | outer_uturn 0.874, recursive_uturn 0.105, reverse_coarser 0.014 |
| delta1000 | 22.66 | 1.01x | 23.36 | 1.04x | 18.36 | 32.1 | 31.1 | 1.00 | 4.97 | 0.000 | outer_uturn 0.885, recursive_uturn 0.115 |
| exhaust-accept | 23.12 | 1.03x | 23.87 | 1.06x | 17.31 | 31.8 | 30.6 | 1.12 | 4.94 | 0.011 | outer_uturn 0.874, recursive_uturn 0.105, reverse_coarser 0.014 |
| cross | 23.51 | 1.04x | 24.28 | 1.08x | 18.16 | 31.6 | 30.5 | 1.14 | 4.94 | 0.012 | outer_uturn 0.870, recursive_uturn 0.106, reverse_coarser 0.015 |
| rhosum | 23.25 | 1.03x | 23.96 | 1.07x | 15.94 | 34.5 | 33.3 | 1.13 | 5.05 | 0.012 | outer_uturn 0.868, recursive_uturn 0.113, reverse_coarser 0.013 |
| exhaust-accept+rhosum | 23.25 | 1.03x | 23.96 | 1.07x | 15.94 | 34.5 | 33.3 | 1.13 | 5.05 | 0.012 | outer_uturn 0.868, recursive_uturn 0.113, reverse_coarser 0.013 |
| levels1-accept | 22.66 | 1.01x | 23.36 | 1.04x | 18.36 | 32.1 | 31.1 | 1.00 | 4.97 | 0.000 | outer_uturn 0.885, recursive_uturn 0.115 |
| levels1-accept+rhosum | 21.58 | 0.96x | 22.22 | 0.99x | 15.69 | 34.6 | 33.6 | 1.00 | 5.06 | 0.000 | outer_uturn 0.874, recursive_uturn 0.126 |
| rhosum+cache | 23.96 | 1.07x | 23.96 | 1.07x | 16.41 | 33.5 | 33.3 | 0.13 | 5.05 | 0.012 | outer_uturn 0.868, recursive_uturn 0.113, reverse_coarser 0.013 |
| exhaust-accept+rhosum+cache | 23.96 | 1.07x | 23.96 | 1.07x | 16.41 | 33.5 | 33.3 | 0.13 | 5.05 | 0.012 | outer_uturn 0.868, recursive_uturn 0.113, reverse_coarser 0.013 |

Per-seed min bulk ESS/grad x1e3: nuts-ref: 21.25/22.50/24.73, default: 23.12/23.34/22.56, rhosum: 24.34/18.73/23.25, exhaust-accept+rhosum: 24.34/18.73/23.25, levels1-accept+rhosum: 21.58/20.25/24.85
