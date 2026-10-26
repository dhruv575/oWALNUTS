# WP67 results (84/84 cells)

**Verdict:** SUPPORTED: recommend a default-flip confirmation study

| clause | holds |
|---|---|
| E | True |
| E_evaluable | True |
| F | True |
| G | True |
| R1 | True |
| R2 | True |
| R3 | True |

## Lotka (trapped chains / 48 per block)

| block | defaults trapped | restart trapped | defaults passes | restart passes | defaults gradients | restart gradients |
|---|---|---|---|---|---|---|
| L1 | 2 | 0 | 10/12 | 12/12 | 5800999 | 3674895 |
| L2 | 0 | 0 | 11/12 | 11/12 | 3403075 | 3403075 |

| block | seed | defaults status | trapped | flags (emulated) | min ratio | R-hat | restart status | restarted | trapped | R-hat | fingerprint |
|---|---|---|---|---|---|---|---|---|---|---|---|
| L1 | 5701101 | ok | [] | [] | 0.9291 | 1.005 | ok | [] | [] | 1.005 | True |
| L1 | 5701102 | ok | [] | [] | 0.7243 | 1.008 | ok | [] | [] | 1.008 | True |
| L1 | 5701103 | ok | [3] | [3] | 0.0023 | 1.592 | ok | [3] | [] | 1.003 | True |
| L1 | 5701104 | ok | [] | [] | 0.9282 | 1.005 | ok | [] | [] | 1.005 | True |
| L1 | 5701105 | ok | [] | [] | 0.5581 | 1.005 | ok | [] | [] | 1.005 | True |
| L1 | 5701106 | ok | [2] | [2] | 0.0254 | 1.595 | ok | [2] | [] | 1.004 | True |
| L1 | 5701107 | ok | [] | [] | 0.6229 | 1.005 | ok | [] | [] | 1.005 | True |
| L1 | 5701108 | ok | [] | [] | 0.4722 | 1.005 | ok | [] | [] | 1.005 | True |
| L1 | 5701109 | ok | [] | [] | 0.8039 | 1.004 | ok | [] | [] | 1.004 | True |
| L1 | 5701110 | ok | [] | [] | 0.8375 | 1.003 | ok | [] | [] | 1.003 | True |
| L1 | 5701111 | ok | [] | [] | 0.6809 | 1.001 | ok | [] | [] | 1.001 | True |
| L1 | 5701112 | ok | [] | [] | 0.4133 | 1.008 | ok | [] | [] | 1.008 | True |
| L2 | 6701201 | ok | [] | [] | 0.6528 | 1.004 | ok | [] | [] | 1.004 | True |
| L2 | 6701202 | ok | [] | [] | 0.7892 | 1.003 | ok | [] | [] | 1.003 | True |
| L2 | 6701203 | ok | [] | [] | 0.8528 | 1.003 | ok | [] | [] | 1.003 | True |
| L2 | 6701204 | ok | [] | [] | 0.8877 | 1.003 | ok | [] | [] | 1.003 | True |
| L2 | 6701205 | ok | [] | [] | 0.7741 | 1.004 | ok | [] | [] | 1.004 | True |
| L2 | 6701206 | ok | [] | [] | 0.3879 | 1.003 | ok | [] | [] | 1.003 | True |
| L2 | 6701207 | ok | [] | [] | 0.9175 | 1.004 | ok | [] | [] | 1.004 | True |
| L2 | 6701208 | ok | [] | [] | 0.4717 | 1.003 | ok | [] | [] | 1.003 | True |
| L2 | 6701209 | ok | [] | [] | 0.6989 | 1.003 | ok | [] | [] | 1.003 | True |
| L2 | 6701210 | ok | [] | [] | 0.5633 | 1.003 | ok | [] | [] | 1.003 | True |
| L2 | 6701211 | ok | [] | [] | 0.6114 | 1.005 | ok | [] | [] | 1.005 | True |
| L2 | 6701212 | ok | [] | [] | 0.6287 | 1.012 | ok | [] | [] | 1.012 | True |

Detector on lotka defaults chains: {'tp': 2, 'fn': 0, 'fp': 0, 'tn': 94, 'fn_not_reached': 0}

## Regression arm

Passes: defaults 12, restart 12 of 18; wrong-chain cells 1 vs 1; firing cells 0; geomean ESS/gradient ratio 1.0000

| model | seed | d passed | d R-hat | d min bulk | d ESS/grad | min step ratio | r passed | restarted | r ESS/grad | fingerprint |
|---|---|---|---|---|---|---|---|---|---|---|
| eight_schools-eight_schools_centered | 6701301 | False | 1.1270 | 24 | 7.925e-05 | 0.805 | False | [] | 7.925e-05 | True |
| eight_schools-eight_schools_centered | 6701302 | False | 1.0268 | 102 | 3.921e-04 | 0.418 | False | [] | 3.921e-04 | True |
| eight_schools-eight_schools_centered | 6701303 | False | 1.0295 | 107 | 5.457e-04 | 0.301 | False | [] | 5.457e-04 | True |
| bball_drive_event_0-hmm_drive_0 | 6701301 | True | 1.0036 | 4055 | 4.100e-02 | 0.905 | True | [] | 4.100e-02 | True |
| bball_drive_event_0-hmm_drive_0 | 6701302 | True | 1.0039 | 3705 | 4.812e-02 | 0.878 | True | [] | 4.812e-02 | True |
| bball_drive_event_0-hmm_drive_0 | 6701303 | True | 1.0017 | 3511 | 3.507e-02 | 0.720 | True | [] | 3.507e-02 | True |
| arma-arma11 | 6701301 | True | 1.0015 | 3846 | 6.945e-02 | 0.459 | True | [] | 6.945e-02 | True |
| arma-arma11 | 6701302 | True | 1.0029 | 3557 | 6.456e-02 | 0.539 | True | [] | 6.456e-02 | True |
| arma-arma11 | 6701303 | True | 1.0008 | 3300 | 5.518e-02 | 0.511 | True | [] | 5.518e-02 | True |
| garch-garch11 | 6701301 | True | 1.0019 | 1823 | 1.904e-02 | 0.575 | True | [] | 1.904e-02 | True |
| garch-garch11 | 6701302 | True | 1.0037 | 1764 | 1.884e-02 | 0.930 | True | [] | 1.884e-02 | True |
| garch-garch11 | 6701303 | True | 1.0039 | 1509 | 1.647e-02 | 0.737 | True | [] | 1.647e-02 | True |
| gp_pois_regr-gp_pois_regr | 6701301 | True | 1.0057 | 781 | 6.318e-04 | 0.979 | True | [] | 6.318e-04 | True |
| gp_pois_regr-gp_pois_regr | 6701302 | False | 1.0106 | 834 | 6.544e-04 | 0.842 | False | [] | 6.544e-04 | True |
| gp_pois_regr-gp_pois_regr | 6701303 | True | 1.0046 | 1006 | 8.358e-04 | 0.491 | True | [] | 8.358e-04 | True |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 6701301 | False | 1.0087 | 715 | 9.153e-03 | 0.743 | False | [] | 9.153e-03 | True |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 6701302 | True | 1.0033 | 921 | 1.151e-02 | 0.785 | True | [] | 1.151e-02 | True |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 6701303 | False | 1.0417 | 88 | 1.071e-03 | 0.736 | False | [] | 1.071e-03 | True |

## Predictions

| id | observed | held |
|---|---|---|
| P1 | 2 | True |
| P2 | 0 | True |
| P3 | {'tp': 2, 'fn': 0, 'fp': 0, 'tn': 94, 'fn_not_reached': 0} | True |
| P4 | 42/42 pairs | True |
| P5 | 0/18 firing; ratio 1.0000 | True |
| P6 | {'grads_defaults': 9204074, 'grads_restart': 7077970, 'restarts': 2} | True |
| P7 | 0 | True |
