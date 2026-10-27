## Accuracy per arm, stream and half (frozen rule)

A scored tick passes iff |P50 err| <= 2 % and |P95 err| <= 5 % against the gated reference and no chain is stuck; a half passes iff >= 95 % of its 80 scored ticks (2 seeds x 40) pass and every seed >= 90 %. Half 1 = ticks 25..1000, half 2 = ticks 1025..2000 (the regime-2 returns enter from tick 1001 on the shift stream). Drift = mean signed P50 error over the half's last 10 scored ticks minus its first 10 (pp, per seed; bound 0.5 pp reported, not gated).

| policy | stream | half | scored | pass pooled | per seed | |P50 err| med / p95 | |P95 err| med / p95 | P95 signed mean | own MCSE P50 | ESS med | stuck | in ref 90 % | drift pp per seed | half |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| frozen | shift | half1 | 6 | 100.0 % | 100 % / 100 % | 0.81 % / 1.59 % | 1.36 % / 3.30 % | -0.24 % | 1.34 % | 1045 | 0 | 90.1 % | -0.76, -2.48 | PASS |
| frozen | shift | half2 | 6 | 50.0 % | 67 % / 33 % | 0.90 % / 2.00 % | 1.21 % / 5.05 % | -0.23 % | 1.00 % | 1055 | 0 | 89.9 % | +1.46, +0.90 | FAIL |
| frozen | control | half1 | 6 | 100.0 % | 100 % / 100 % | 0.85 % / 1.63 % | 1.39 % / 3.07 % | -0.00 % | 1.34 % | 1045 | 0 | 90.1 % | -1.10, -2.83 | PASS |
| frozen | control | half2 | 6 | 83.3 % | 100 % / 67 % | 0.99 % / 1.91 % | 1.25 % / 5.59 % | -0.18 % | 1.00 % | 1055 | 0 | 89.8 % | +1.27, +0.70 | FAIL |
| m100 | shift | half1 | 6 | 100.0 % | 100 % / 100 % | 0.90 % / 1.86 % | 1.79 % / 3.26 % | 1.29 % | 1.34 % | 1141 | 0 | 89.6 % | -0.61, -0.33 | PASS |
| m100 | shift | half2 | 6 | 83.3 % | 100 % / 67 % | 1.18 % / 2.42 % | 0.86 % / 1.63 % | 0.65 % | 1.27 % | 1161 | 0 | 89.7 % | +0.08, +2.87 | FAIL |
| m100 | control | half1 | 6 | 100.0 % | 100 % / 100 % | 0.95 % / 1.67 % | 1.79 % / 3.53 % | 1.53 % | 1.34 % | 1141 | 0 | 89.5 % | -0.96, -0.67 | PASS |
| m100 | control | half2 | 6 | 66.7 % | 100 % / 33 % | 1.24 % / 2.34 % | 1.27 % / 1.45 % | 0.69 % | 1.27 % | 1161 | 0 | 89.7 % | -0.11, +2.67 | FAIL |
| m500 | shift | half1 | 6 | 100.0 % | 100 % / 100 % | 0.81 % / 1.59 % | 1.36 % / 3.30 % | -0.24 % | 1.34 % | 1045 | 0 | 90.1 % | -0.76, -2.48 | PASS |
| m500 | shift | half2 | 6 | 83.3 % | 100 % / 67 % | 0.88 % / 2.58 % | 1.32 % / 3.76 % | -1.30 % | 1.38 % | 1068 | 0 | 90.2 % | +1.58, +1.43 | FAIL |
| m500 | control | half1 | 6 | 100.0 % | 100 % / 100 % | 0.85 % / 1.63 % | 1.39 % / 3.07 % | -0.00 % | 1.34 % | 1045 | 0 | 90.1 % | -1.10, -2.83 | PASS |
| m500 | control | half2 | 6 | 83.3 % | 100 % / 67 % | 0.77 % / 2.68 % | 1.20 % / 4.03 % | -1.26 % | 1.38 % | 1068 | 0 | 90.3 % | +1.39, +1.23 | FAIL |
| trig | shift | half1 | 6 | 100.0 % | 100 % / 100 % | 0.81 % / 1.59 % | 1.36 % / 3.30 % | -0.24 % | 1.34 % | 1045 | 0 | 90.1 % | -0.76, -2.48 | PASS |
| trig | shift | half2 | 6 | 50.0 % | 67 % / 33 % | 0.90 % / 2.00 % | 1.21 % / 5.05 % | -0.23 % | 1.00 % | 1055 | 0 | 89.9 % | +1.46, +0.90 | FAIL |
| trig | control | half1 | 6 | 100.0 % | 100 % / 100 % | 0.85 % / 1.63 % | 1.39 % / 3.07 % | -0.00 % | 1.34 % | 1045 | 0 | 90.1 % | -1.10, -2.83 | PASS |
| trig | control | half2 | 6 | 83.3 % | 100 % / 67 % | 0.99 % / 1.91 % | 1.25 % / 5.59 % | -0.18 % | 1.00 % | 1055 | 0 | 89.8 % | +1.27, +0.70 | FAIL |

Verdict: {"frozen_holds": false, "policies_passing_both_streams": [], "per_policy": {"frozen": {"shift": false, "control": false}, "m100": {"shift": false, "control": false}, "m500": {"shift": false, "control": false}, "trig": {"shift": false, "control": false}}, "per_half": {"frozen": {"shift": {"half1": true, "half2": false}, "control": {"half1": true, "half2": false}}, "m100": {"shift": {"half1": true, "half2": false}, "control": {"half1": true, "half2": false}}, "m500": {"shift": {"half1": true, "half2": false}, "control": {"half1": true, "half2": false}}, "trig": {"shift": {"half1": true, "half2": false}, "control": {"half1": true, "half2": false}}}}

## Latency and re-adaptation per arm and stream (all 2,000 ticks; tick 0 excluded)

| policy | stream | median s | P99 s | max s | < 0.4 s | median half 1 | median half 2 | re-adaptations per seed | re-adapt tick median s | re-adapt tick max s | first re-adapt after the shift | re-adapt chain fallbacks | re-adapt errors | cost ratio by 250-tick block (seed 1) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| frozen | shift | 0.149 | 0.176 | 0.182 | 100.0 % | 0.149 | 0.148 | [0, 0] | n/a | n/a | [None, None] | 0 | 0 | 1.00 |
| frozen | control | 0.131 | 0.192 | 0.192 | 100.0 % | 0.132 | 0.130 | [0, 0] | n/a | n/a | [None, None] | 0 | 0 | 1.00 |
| m100 | shift | 0.273 | 0.682 | 0.707 | 92.5 % | 0.155 | 0.276 | [3, 3] | 0.662 | 0.707 | [40, 40] | 0 | 0 | 1.75 |
| m100 | control | 0.254 | 0.665 | 0.670 | 95.0 % | 0.134 | 0.256 | [3, 3] | 0.651 | 0.670 | [40, 40] | 0 | 0 | 1.75 |
| m500 | shift | 0.154 | 0.402 | 0.574 | 98.3 % | 0.151 | 0.269 | [1, 1] | 0.570 | 0.574 | [40, 40] | 0 | 0 | 1.41 |
| m500 | control | 0.132 | 0.377 | 0.545 | 98.3 % | 0.129 | 0.250 | [1, 1] | 0.545 | 0.545 | [40, 40] | 0 | 0 | 1.41 |
| trig | shift | 0.150 | 0.159 | 0.159 | 100.0 % | 0.150 | 0.150 | [0, 0] | n/a | n/a | [None, None] | 0 | 0 | 1.00 |
| trig | control | 0.131 | 0.141 | 0.142 | 100.0 % | 0.132 | 0.131 | [0, 0] | n/a | n/a | [None, None] | 0 | 0 | 1.00 |

## Trigger arm: firing ticks (trailing cost > 1.5 x post-adaptation baseline, or > 5 % unchanged positions)

| stream | seed | fired at ticks | max trailing/baseline ratio | re-adaptations |
|---|---|---|---|---|
| shift | 990963 | [] | 1.010 | 0 |
| shift | 990964 | [] | 1.008 | 0 |
| control | 990963 | [] | 1.010 | 0 |
| control | 990964 | [] | 1.008 | 0 |

## Gated reference (4 x 2,000/20,000 on the tick's 250-return window)

| stream | ticks planned | ok | gate failed (both seeds) | second seed used | ticks with a flagged chain dropped | min chains kept | max R-hat(h_next) | rel. MCSE P50 med / max (half 1) | (half 2) | rel. MCSE P95 med / max (half 1) | (half 2) | min ESS | median wall s | total min |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| shift | 7 | 7 | 0 | 0 | 0 | 4 | 1.0001 | 0.11 % / 0.16 % | 0.11 % / 0.12 % | 0.25 % / 0.28 % | 0.24 % / 0.26 % | 89285 | 9.112 | 1.1 |
| control | 7 | 7 | 0 | 0 | 1 | 3 | 1.0001 | 0.13 % / 0.15 % | 0.11 % / 0.12 % | 0.27 % / 0.29 % | 0.25 % / 0.25 % | 81117 | 9.070 | 4.0 |

## Tick-0 fits (4 x 1,000/1,000 at defaults; outside the latency statistics)

| cell | wall s | flagged chains | kept | tick-0 P50 err | tick-0 P95 err | accurate |
|---|---|---|---|---|---|---|
| warm-frozen-shift-s960101 | 2.910 | [] | [0, 1, 2, 3] | -0.05 % | 0.33 % | True |
| warm-m100-shift-s960101 | 2.881 | [] | [0, 1, 2, 3] | -0.05 % | 0.33 % | True |
| warm-m500-shift-s960101 | 2.877 | [] | [0, 1, 2, 3] | -0.05 % | 0.33 % | True |
| warm-trig-shift-s960101 | 2.875 | [] | [0, 1, 2, 3] | -0.05 % | 0.33 % | True |
| warm-frozen-shift-s960102 | 2.762 | [] | [0, 1, 2, 3] | -0.59 % | 2.40 % | True |
| warm-m100-shift-s960102 | 2.775 | [] | [0, 1, 2, 3] | -0.59 % | 2.40 % | True |
| warm-m500-shift-s960102 | 2.789 | [] | [0, 1, 2, 3] | -0.59 % | 2.40 % | True |
| warm-trig-shift-s960102 | 2.788 | [] | [0, 1, 2, 3] | -0.59 % | 2.40 % | True |
| warm-frozen-control-s960101 | 2.878 | [] | [0, 1, 2, 3] | 0.01 % | 0.90 % | True |
| warm-m100-control-s960101 | 2.896 | [] | [0, 1, 2, 3] | 0.01 % | 0.90 % | True |
| warm-m500-control-s960101 | 2.874 | [] | [0, 1, 2, 3] | 0.01 % | 0.90 % | True |
| warm-trig-control-s960101 | 2.911 | [] | [0, 1, 2, 3] | 0.01 % | 0.90 % | True |
| warm-frozen-control-s960102 | 2.797 | [] | [0, 1, 2, 3] | -0.53 % | 2.98 % | True |
| warm-m100-control-s960102 | 2.753 | [] | [0, 1, 2, 3] | -0.53 % | 2.98 % | True |
| warm-m500-control-s960102 | 2.760 | [] | [0, 1, 2, 3] | -0.53 % | 2.98 % | True |
| warm-trig-control-s960102 | 2.771 | [] | [0, 1, 2, 3] | -0.53 % | 2.98 % | True |

## Per-cell step ratio (mean 2^-level) and cost ratio by 250-tick block

| cell | cost ratio per block (vs ticks 1-20) | step ratio per block | max unchanged fraction |
|---|---|---|---|
| warm-frozen-shift-s960101 | 1.00 | 0.988 | 0.0163 |
| warm-m100-shift-s960101 | 1.75 | 0.983 | 0.0163 |
| warm-m500-shift-s960101 | 1.41 | 0.985 | 0.0163 |
| warm-trig-shift-s960101 | 1.00 | 0.988 | 0.0163 |
| warm-frozen-shift-s960102 | 1.00 | 0.989 | 0.0112 |
| warm-m100-shift-s960102 | 1.66 | 0.985 | 0.0150 |
| warm-m500-shift-s960102 | 1.37 | 0.984 | 0.0163 |
| warm-trig-shift-s960102 | 1.00 | 0.989 | 0.0112 |
| warm-frozen-control-s960101 | 1.00 | 0.988 | 0.0163 |
| warm-m100-control-s960101 | 1.75 | 0.983 | 0.0163 |
| warm-m500-control-s960101 | 1.41 | 0.985 | 0.0163 |
| warm-trig-control-s960101 | 1.00 | 0.988 | 0.0163 |
| warm-frozen-control-s960102 | 1.00 | 0.989 | 0.0112 |
| warm-m100-control-s960102 | 1.66 | 0.985 | 0.0150 |
| warm-m500-control-s960102 | 1.37 | 0.984 | 0.0163 |
| warm-trig-control-s960102 | 1.00 | 0.989 | 0.0112 |
