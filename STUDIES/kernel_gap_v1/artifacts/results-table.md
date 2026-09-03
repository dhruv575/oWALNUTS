# kernel_gap_v1 — results

Seed medians over seeds 84201, 84202; 4 chains x 2000 draws at CmdStan's adapted step, inverse metric and post-warmup starts per chain. ESS = minimum over unconstrained coordinates of bulk ESS. `x ref` = ratio to `nuts-ref` on the same seed, seed median.

| model | arm | ESS/grad x1e3 | x ref | ESS/orbit | x ref | leaves/orbit | x ref | grads/leaf | x ref | depth | stop causes | sel=init | rel. displacement | refined leaves | non-leaf grads/orbit (init / rejected / reverse) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| earnings__logearn_interaction | nuts-ref | 1.622 | 1.00 | 0.256 | 1.00 | 158.0 | 1.00 | 1.000 | 1.00 | 6.33 | uturn 100% | 0.001 | 0.517 | 0.0% | 0.00 / 0.00 / 0.00 |
| earnings__logearn_interaction | walnuts | 1.331 | 0.83 | 0.054 | 0.21 | 40.5 | 0.26 | 1.005 | 1.01 | 4.21 | recursive_uturn 67%, outer_uturn 30%, reverse_coarser 3% | 0.026 | 0.596 | 0.1% | 0.00 / 0.06 / 0.06 |
| earnings__logearn_interaction | walnuts+cross | 0.969 | 0.62 | 0.036 | 0.15 | 36.6 | 0.23 | 1.006 | 1.01 | 4.02 | recursive_uturn 62%, outer_uturn 36%, reverse_coarser 2% | 0.026 | 0.598 | 0.1% | 0.00 / 0.06 / 0.06 |
| earnings__logearn_interaction | walnuts+rhosum | 1.446 | 0.90 | 0.219 | 0.86 | 150.7 | 0.95 | 1.003 | 1.00 | 6.73 | recursive_uturn 54%, outer_uturn 42%, reverse_coarser 5% | 0.013 | 0.513 | 0.1% | 0.00 / 0.15 / 0.15 |
| earnings__logearn_interaction | walnuts+delta1000 | 1.096 | 0.68 | 0.044 | 0.17 | 40.0 | 0.25 | 1.000 | 1.00 | 4.21 | recursive_uturn 69%, outer_uturn 31% | 0.021 | 0.597 | 0.0% | 0.00 / 0.00 / 0.00 |
| earnings__logearn_interaction | walnuts+levels1 | 1.096 | 0.68 | 0.044 | 0.17 | 40.0 | 0.25 | 1.000 | 1.00 | 4.21 | recursive_uturn 69%, outer_uturn 31% | 0.021 | 0.597 | 0.0% | 0.00 / 0.00 / 0.00 |
| earnings__logearn_interaction | walnuts+levels1+rhosum | 1.562 | 0.97 | 0.244 | 0.96 | 156.1 | 0.99 | 1.000 | 1.00 | 6.89 | recursive_uturn 58%, outer_uturn 42% | 0.001 | 0.517 | 0.0% | 0.00 / 0.00 / 0.00 |
| earnings__logearn_interaction | walnuts+accept | 1.331 | 0.83 | 0.054 | 0.21 | 40.5 | 0.26 | 1.005 | 1.01 | 4.21 | recursive_uturn 67%, outer_uturn 30%, reverse_coarser 3% | 0.026 | 0.596 | 0.1% | 0.00 / 0.06 / 0.06 |
| kidiq__kidscore_momhsiq | nuts-ref | 12.902 | 1.00 | 0.379 | 1.00 | 29.4 | 1.00 | 1.000 | 1.00 | 4.41 | uturn 100% | 0.003 | 0.532 | 0.0% | 0.00 / 0.00 / 0.00 |
| kidiq__kidscore_momhsiq | walnuts | 8.993 | 0.70 | 0.131 | 0.35 | 14.5 | 0.49 | 1.009 | 1.01 | 3.48 | recursive_uturn 58%, outer_uturn 40%, reverse_coarser 2% | 0.028 | 0.620 | 0.1% | 0.00 / 0.04 / 0.04 |
| kidiq__kidscore_momhsiq | walnuts+cross | 7.290 | 0.56 | 0.099 | 0.26 | 13.5 | 0.46 | 1.009 | 1.01 | 3.36 | recursive_uturn 54%, outer_uturn 44%, reverse_coarser 1% | 0.031 | 0.627 | 0.2% | 0.00 / 0.04 / 0.04 |
| kidiq__kidscore_momhsiq | walnuts+rhosum | 10.823 | 0.84 | 0.314 | 0.83 | 28.7 | 0.98 | 1.010 | 1.01 | 4.72 | outer_uturn 61%, recursive_uturn 35%, reverse_coarser 4% | 0.010 | 0.533 | 0.2% | 0.00 / 0.09 / 0.09 |
| kidiq__kidscore_momhsiq | walnuts+delta1000 | 9.593 | 0.74 | 0.138 | 0.36 | 14.4 | 0.49 | 1.000 | 1.00 | 3.47 | recursive_uturn 58%, outer_uturn 42% | 0.024 | 0.628 | 0.0% | 0.00 / 0.00 / 0.00 |
| kidiq__kidscore_momhsiq | walnuts+levels1 | 9.593 | 0.74 | 0.138 | 0.36 | 14.4 | 0.49 | 1.000 | 1.00 | 3.47 | recursive_uturn 58%, outer_uturn 42% | 0.024 | 0.628 | 0.0% | 0.00 / 0.00 / 0.00 |
| kidiq__kidscore_momhsiq | walnuts+levels1+rhosum | 12.634 | 0.98 | 0.368 | 0.97 | 29.1 | 0.99 | 1.000 | 1.00 | 4.77 | outer_uturn 63%, recursive_uturn 37% | 0.003 | 0.532 | 0.0% | 0.00 / 0.00 / 0.00 |
| kidiq__kidscore_momhsiq | walnuts+accept | 8.993 | 0.70 | 0.131 | 0.35 | 14.5 | 0.49 | 1.009 | 1.01 | 3.48 | recursive_uturn 58%, outer_uturn 40%, reverse_coarser 2% | 0.028 | 0.620 | 0.1% | 0.00 / 0.04 / 0.04 |
| mesquite__logmesquite_logvash | nuts-ref | 7.403 | 1.00 | 0.362 | 1.00 | 48.9 | 1.00 | 1.000 | 1.00 | 5.19 | uturn 100% | 0.000 | 0.516 | 0.0% | 0.00 / 0.00 / 0.00 |
| mesquite__logmesquite_logvash | walnuts | 6.604 | 0.89 | 0.268 | 0.74 | 40.1 | 0.82 | 1.010 | 1.01 | 5.15 | outer_uturn 49%, recursive_uturn 46%, reverse_coarser 5% | 0.012 | 0.522 | 0.2% | 0.00 / 0.11 / 0.11 |
| mesquite__logmesquite_logvash | walnuts+cross | 6.197 | 0.84 | 0.239 | 0.66 | 38.3 | 0.78 | 1.010 | 1.01 | 5.05 | outer_uturn 50%, recursive_uturn 45%, reverse_coarser 5% | 0.012 | 0.526 | 0.2% | 0.00 / 0.11 / 0.11 |
| mesquite__logmesquite_logvash | walnuts+rhosum | 7.084 | 0.96 | 0.335 | 0.93 | 46.6 | 0.95 | 1.014 | 1.01 | 5.42 | outer_uturn 61%, recursive_uturn 31%, reverse_coarser 7% | 0.010 | 0.513 | 0.2% | 0.00 / 0.19 / 0.19 |
| mesquite__logmesquite_logvash | walnuts+delta1000 | 6.598 | 0.89 | 0.270 | 0.75 | 40.9 | 0.84 | 1.000 | 1.00 | 5.19 | outer_uturn 52%, recursive_uturn 48% | 0.002 | 0.525 | 0.0% | 0.00 / 0.00 / 0.00 |
| mesquite__logmesquite_logvash | walnuts+levels1 | 6.598 | 0.89 | 0.270 | 0.75 | 40.9 | 0.84 | 1.000 | 1.00 | 5.19 | outer_uturn 52%, recursive_uturn 48% | 0.002 | 0.525 | 0.0% | 0.00 / 0.00 / 0.00 |
| mesquite__logmesquite_logvash | walnuts+levels1+rhosum | 7.453 | 1.01 | 0.366 | 1.01 | 49.1 | 1.00 | 1.000 | 1.00 | 5.54 | outer_uturn 66%, recursive_uturn 34% | 0.000 | 0.516 | 0.0% | 0.00 / 0.00 / 0.00 |
| mesquite__logmesquite_logvash | walnuts+accept | 6.604 | 0.89 | 0.268 | 0.74 | 40.1 | 0.82 | 1.010 | 1.01 | 5.15 | outer_uturn 49%, recursive_uturn 46%, reverse_coarser 5% | 0.012 | 0.522 | 0.2% | 0.00 / 0.11 / 0.11 |
| nes2000__nes | nuts-ref | 9.989 | 1.00 | 0.499 | 1.00 | 49.9 | 1.00 | 1.000 | 1.00 | 5.33 | uturn 100% | 0.000 | 0.512 | 0.0% | 0.00 / 0.00 / 0.00 |
| nes2000__nes | walnuts | 6.195 | 0.62 | 0.208 | 0.42 | 33.4 | 0.67 | 1.005 | 1.00 | 4.72 | outer_uturn 49%, recursive_uturn 49%, reverse_coarser 2% | 0.013 | 0.538 | 0.1% | 0.00 / 0.05 / 0.05 |
| nes2000__nes | walnuts+cross | 6.451 | 0.65 | 0.204 | 0.41 | 31.5 | 0.63 | 1.004 | 1.00 | 4.60 | outer_uturn 51%, recursive_uturn 48%, reverse_coarser 1% | 0.010 | 0.543 | 0.1% | 0.00 / 0.04 / 0.04 |
| nes2000__nes | walnuts+rhosum | 8.782 | 0.88 | 0.428 | 0.86 | 48.3 | 0.97 | 1.008 | 1.01 | 5.49 | outer_uturn 72%, recursive_uturn 24%, reverse_coarser 4% | 0.008 | 0.513 | 0.2% | 0.00 / 0.12 / 0.12 |
| nes2000__nes | walnuts+delta1000 | 7.064 | 0.71 | 0.240 | 0.48 | 33.9 | 0.68 | 1.000 | 1.00 | 4.77 | recursive_uturn 51%, outer_uturn 49% | 0.005 | 0.547 | 0.0% | 0.00 / 0.00 / 0.00 |
| nes2000__nes | walnuts+levels1 | 7.064 | 0.71 | 0.240 | 0.48 | 33.9 | 0.68 | 1.000 | 1.00 | 4.77 | recursive_uturn 51%, outer_uturn 49% | 0.005 | 0.547 | 0.0% | 0.00 / 0.00 / 0.00 |
| nes2000__nes | walnuts+levels1+rhosum | 8.959 | 0.90 | 0.448 | 0.90 | 50.0 | 1.00 | 1.000 | 1.00 | 5.59 | outer_uturn 75%, recursive_uturn 25% | 0.000 | 0.510 | 0.0% | 0.00 / 0.00 / 0.00 |
| nes2000__nes | walnuts+accept | 6.195 | 0.62 | 0.208 | 0.42 | 33.4 | 0.67 | 1.005 | 1.00 | 4.72 | outer_uturn 49%, recursive_uturn 49%, reverse_coarser 2% | 0.013 | 0.538 | 0.1% | 0.00 / 0.05 / 0.05 |
| garch__garch11 | nuts-ref | 43.572 | 1.00 | 0.484 | 1.00 | 11.1 | 1.00 | 1.000 | 1.00 | 3.19 | uturn 100% | 0.005 | 0.563 | 0.0% | 0.00 / 0.00 / 0.00 |
| garch__garch11 | walnuts | 35.334 | 0.81 | 0.287 | 0.59 | 7.8 | 0.70 | 1.040 | 1.04 | 2.98 | outer_uturn 55%, recursive_uturn 41%, reverse_coarser 4% | 0.023 | 0.611 | 0.6% | 0.00 / 0.09 / 0.09 |
| garch__garch11 | walnuts+cross | 32.232 | 0.74 | 0.246 | 0.51 | 7.3 | 0.66 | 1.043 | 1.04 | 2.89 | outer_uturn 57%, recursive_uturn 39%, reverse_coarser 4% | 0.025 | 0.615 | 0.7% | 0.00 / 0.09 / 0.09 |
| garch__garch11 | walnuts+rhosum | 38.552 | 0.89 | 0.432 | 0.89 | 10.8 | 0.97 | 1.042 | 1.04 | 3.45 | outer_uturn 66%, recursive_uturn 29%, reverse_coarser 6% | 0.016 | 0.560 | 0.7% | 0.00 / 0.13 / 0.13 |
| garch__garch11 | walnuts+delta1000 | 35.536 | 0.82 | 0.283 | 0.58 | 7.9 | 0.72 | 1.000 | 1.00 | 2.99 | outer_uturn 56%, recursive_uturn 44% | 0.017 | 0.615 | 0.0% | 0.00 / 0.00 / 0.00 |
| garch__garch11 | walnuts+levels1 | 35.536 | 0.82 | 0.283 | 0.58 | 7.9 | 0.72 | 1.000 | 1.00 | 2.99 | outer_uturn 56%, recursive_uturn 44% | 0.017 | 0.615 | 0.0% | 0.00 / 0.00 / 0.00 |
| garch__garch11 | walnuts+levels1+rhosum | 41.843 | 0.96 | 0.463 | 0.96 | 11.1 | 1.00 | 1.000 | 1.00 | 3.49 | outer_uturn 69%, recursive_uturn 31% | 0.005 | 0.561 | 0.0% | 0.00 / 0.00 / 0.00 |
| garch__garch11 | walnuts+accept | 35.334 | 0.81 | 0.287 | 0.59 | 7.8 | 0.70 | 1.040 | 1.04 | 2.98 | outer_uturn 55%, recursive_uturn 41%, reverse_coarser 4% | 0.023 | 0.611 | 0.6% | 0.00 / 0.09 / 0.09 |
| arK__arK | nuts-ref | 21.229 | 1.00 | 0.698 | 1.00 | 32.9 | 1.00 | 1.000 | 1.00 | 4.80 | uturn 100% | 0.000 | 0.518 | 0.0% | 0.00 / 0.00 / 0.00 |
| arK__arK | walnuts | 16.716 | 0.79 | 0.511 | 0.73 | 30.4 | 0.92 | 1.007 | 1.01 | 4.81 | outer_uturn 68%, recursive_uturn 30%, reverse_coarser 2% | 0.006 | 0.524 | 0.1% | 0.00 / 0.06 / 0.06 |
| arK__arK | walnuts+cross | 16.851 | 0.79 | 0.500 | 0.72 | 29.5 | 0.90 | 1.007 | 1.01 | 4.76 | outer_uturn 67%, recursive_uturn 31%, reverse_coarser 2% | 0.008 | 0.529 | 0.1% | 0.00 / 0.06 / 0.06 |
| arK__arK | walnuts+rhosum | 19.843 | 0.93 | 0.644 | 0.92 | 32.2 | 0.98 | 1.009 | 1.01 | 4.95 | outer_uturn 78%, recursive_uturn 19%, reverse_coarser 3% | 0.006 | 0.515 | 0.2% | 0.00 / 0.08 / 0.08 |
| arK__arK | walnuts+delta1000 | 16.970 | 0.80 | 0.524 | 0.75 | 30.9 | 0.94 | 1.000 | 1.00 | 4.86 | outer_uturn 69%, recursive_uturn 31% | 0.001 | 0.524 | 0.0% | 0.00 / 0.00 / 0.00 |
| arK__arK | walnuts+levels1 | 16.970 | 0.80 | 0.524 | 0.75 | 30.9 | 0.94 | 1.000 | 1.00 | 4.86 | outer_uturn 69%, recursive_uturn 31% | 0.001 | 0.524 | 0.0% | 0.00 / 0.00 / 0.00 |
| arK__arK | walnuts+levels1+rhosum | 18.252 | 0.86 | 0.601 | 0.86 | 32.9 | 1.00 | 1.000 | 1.00 | 5.00 | outer_uturn 81%, recursive_uturn 19% | 0.001 | 0.519 | 0.0% | 0.00 / 0.00 / 0.00 |
| arK__arK | walnuts+accept | 16.716 | 0.79 | 0.511 | 0.73 | 30.4 | 0.92 | 1.007 | 1.01 | 4.81 | outer_uturn 68%, recursive_uturn 30%, reverse_coarser 2% | 0.006 | 0.524 | 0.1% | 0.00 / 0.06 / 0.06 |

## CmdStan's own sampling run (the source of step, metric and starts; 4 x 1,000 retained, constrained-parameter ESS)

| model | h (per chain) | leapfrogs/orbit | depth | min bulk ESS | ESS/orbit | ESS/grad x1e3 |
|---|---|---:|---:|---:|---:|---:|
| earnings__logearn_interaction | 0.0184, 0.0179, 0.0181, 0.0177 | 155.4 | 6.32 | 1059 | 0.265 | 1.704 |
| kidiq__kidscore_momhsiq | 0.1130, 0.1109, 0.1152, 0.1020 | 29.2 | 4.40 | 1534 | 0.383 | 13.117 |
| mesquite__logmesquite_logvash | 0.0736, 0.0860, 0.0752, 0.0683 | 49.6 | 5.21 | 1344 | 0.336 | 6.778 |
| nes2000__nes | 0.0886, 0.0831, 0.0737, 0.0800 | 49.1 | 5.32 | 1620 | 0.405 | 8.249 |
| garch__garch11 | 0.3058, 0.3883, 0.3171, 0.2961 | 11.0 | 3.17 | 2002 | 0.501 | 45.329 |
| arK__arK | 0.1264, 0.1093, 0.1040, 0.1269 | 33.0 | 4.81 | 2714 | 0.679 | 20.552 |

## Geometric mean over the six models of the seed-median ratios to `nuts-ref`

| arm | ESS/grad | ESS/orbit | leaves/orbit | grads/leaf | orbits/grad |
|---|---:|---:|---:|---:|---:|
| walnuts | 0.767 | 0.464 | 0.597 | 1.012 | 1.655 |
| walnuts+cross | 0.693 | 0.394 | 0.561 | 1.013 | 1.761 |
| walnuts+rhosum | 0.899 | 0.881 | 0.967 | 1.014 | 1.020 |
| walnuts+delta1000 | 0.770 | 0.463 | 0.602 | 1.000 | 1.662 |
| walnuts+levels1 | 0.770 | 0.463 | 0.602 | 1.000 | 1.662 |
| walnuts+levels1+rhosum | 0.946 | 0.942 | 0.997 | 1.000 | 1.003 |
| walnuts+accept | 0.767 | 0.464 | 0.597 | 1.012 | 1.655 |
