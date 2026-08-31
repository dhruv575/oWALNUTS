# Results — invalid-evaluation parity v1 (kernel v10)

## Truncated Gaussian (recoverable-error wall at x0 = 0)

| functional | R-hat | bulk ESS | tail ESS | mean (exact) | z | variance (exact) | z |
|---|---:|---:|---:|---:|---:|---:|---:|
| x0 | 1.0001 | 47895 | 59391 | 0.8046 (0.7979) | +2.41 | 0.3684 (0.3634) | +2.23 |
| x1 | 1.0001 | 44924 | 59053 | -0.0038 (0.0000) | -0.80 | 1.0097 (1.0000) | +1.62 |

Retained: 5061666 recoverable failures = 5061666 zero-density evaluations; 0 invalid-evaluation stops; 0 divergences; 145836 exhaustion stops of 200000 transitions; stops {'outer_uturn': 37162, 'recursive_uturn': 425, 'refinement_exhausted': 145836, 'reverse_coarser_accepted': 16577}; gates PASS ({'all_draws_inside': True, 'invalid_evaluation_stops': True, 'divergences': True, 'recoverable_failures_present': True, 'zero_density_equals_recoverable': True, 'rhat': True, 'bulk_ess': True, 'tail_ess': True, 'moments': True}).

## Funnel gate at paper tuning (v10)

```
{
 "schema": "owalnuts-funnel-bias-fix-summary/v1",
 "executed_utc_date": "2026-08-31"
}
```

## Stock–Watson arms F and A without -inf emulation

```
{
 "schema": "owalnuts-paper-stock-watson-summary/v1",
 "arms": {
  "F": {
   "arm": "F",
   "chains": 4,
   "retained_per_chain": 2000,
   "settings": {
    "discarded": 500,
    "divergence_threshold": 1000.0,
    "max_depth": 10,
    "max_error": 0.3,
    "max_refinement_levels": 8,
    "min_micro_steps": 8,
    "paper_adaptation": null,
    "retained": 2000,
    "step_size": 0.1
   },
   "algorithm_revision": "walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10",
   "wall_seconds": 48.7453494,
   "threads": 4,
   "functionals": {
    "log_sigma2": {
     "rhat": 1.0010721815116994,
     "bulk_ess": 2769.123309216937,
     "tail_ess": 4054.2787484673586,
     "mean": -2.313702708371058,
     "sd": 0.27945216130872136,
     "per_chain_mean": [
      -2.3230096608458783,
      -2.313115539907606,
      -2.324239835982564,
      -2.2944457967481857
     ]
    },
    "z_1": {
     "rhat": 1.0021417335481129,
     "bulk_ess": 2767.7306363496164,
     "tail_ess": 2917.7098203829023,
     "mean": -6.057841857215983,
     "sd": 1.7671313743557127,
     "per_chain_mean": [
      -6.034050922199604,
      -6.036368109217508,
      -6.070771170645159,
      -6.090177226801661
     ]
    },
    "z_last": {
     "rhat": 1.001114767506615,
     "bulk_ess": 2267.6947244624694,
     "tail_ess": 2453.054009386073,
     "mean": -3.1594683746101118,
     "sd": 2.550186743385052,
     "per_chain_mean": [
      -2.9774874333296166,
      -3.2502714446743712,
      -3.236993579178805,
      -3.1731210412576556
     ]
    },
    "x_1": {
     "rhat": 1.000723849261248,
     "bulk_ess": 6820.226428992428,
     "tail_ess": 5156.37845559256,
     "mean": -1.2387770005492549,
     "sd": 0.703671790471397,
     "per_chain_mean": [
      -1.211336911640719,
      -1.2291274170320994,
      -1.2682948366038678,
      -1.2463488369203324
     ]
    },
    "x_last": {
     "rhat": 1.0004370950374981,
     "bulk_ess": 5084.9170025974645,
     "tail_ess": 4951.181664362849,
     "mean": 2.0945505694101647,
     "sd": 0.7791401791309638,
     "per_chain_mean": [
      2.0675034475971654,
      2.093483333866179,
      2.1244551308214685,
      2.092760365355846
     ]
    },
    "mu_last": {
     "rhat": 1.0003588761389999,
     "bulk_ess": 4325.922943293187,
     "tail_ess": 5016.797436007724,
     "mean": 1.0629875093932442,
     "sd": 1.1060374278872391,
     "per_chain_mean": [
      1.0838424906678332,
      1.043796296700721,
      1.1040059095589894,
      1.0203053406454332
     ]
    },
    "z_mean": {
     "rhat": 1.0005753661526542,
     "bulk_ess": 1659.7622843258248,
     "tail_ess": 3399.7495977482854,
     "mean": -4.529830097902865,
     "sd": 0.561229895284009,
     "per_chain_mean": [
      -4.508445707517279,
      -4.54199139892574,
      -4.54427416515373,
      -4.524609120014707
     ]
    },
    "x_mean": {
     "rhat": 1.0069047940738105,
     "bulk_ess": 693.1729435876553,
     "tail_ess": 678.1208652956711,
     "mean": -2.034954393136433,
     "sd": 0.17028237704012528,
     "per_chain_mean": [
      -2.0247272390141,
      -2.0256826702423023,
      -2.029085443352644,
      -2.0603222199366855
     ]
    },
    "mu_mean": {
     "rhat": 1.0002126886272018,
     "bulk_ess": 5851.460671764531,
     "tail_ess": 5711.483182068395,
     "mean": 1.3709333435882938,
     "sd": 0.07719866717487942,
     "per_chain_mean": [
      1.3698709613375009,
      1.3700592056782488,
      1.3727380863098424,
      1.3710651210275833
     ]
    }
   },
   "health": {
    "target_calls": 20574872,
    "divergences": 0,
    "invalid_evaluation_stops": 0,
    "refinement_exhaustion_stops": 1,
    "reverse_coarser_stops": 3626,
    "maximum_depth_stops": 0,
    "leaves_built": 39133,
    "forward_micro_steps": 14128576,
    "retained_transitions": 8000,
    "maximum_depth_rate": 0.0,
    "mean_target_calls_per_transition": 2571.859
   },
   "depth_histogram": [
    0,
    866,
    1222,
    5912,
    0,
    0,
    0,
    0,
    0,
    0,
    0
   ],
   "selected_refinement_level_histogram": [
    0,
    0,
    0,
    26,
    3643,
    3168,
    275,
    22,
    0
   ],
   "hamiltonian_range": {
    "count": 8000,
    "q50": 0.7374268872534913,
    "q90": 2.3024674512187406,
    "q99": 5.934290208248014,
    "max": 18.214601998663284,
    "fraction_gt_1": 0.369125,
    "fraction_gt_2": 0.13,
    "fraction_gt_5": 0.01525
   },
   "max_abs_energy_error": {
    "count": 8000,
    "q50": 0.47837543028623486,
    "q90": 1.5004025115495438,
    "q99": 4.522156331158176,
    "max": 17.260389037211212,
    "fraction_gt_1": 0.204125,
    "fraction_gt_2": 0.05975,
    "fraction_gt_5": 0.008
   },
   "final_tuning_per_chain": [
    {
     "max_error": 0.3,
     "max_refinement_levels": 8,
     "min_micro_steps": 8,
     "step_size": 0.1
    },
    {
     "max_error": 0.3,
     "max_refinement_levels": 8,
     "min_micro_steps": 8,
     "step_size": 0.1
    },
    {
     "max_error": 0.3,
     "max_refinement_levels": 8,
     "min_micro_steps": 8,
     "step_size": 0.1
    },
    {
     "max_error": 0.3,
     "max_refinement_levels": 8,
     "min_micro_steps": 8,
     "step_size": 0.1
    }
   ],
   "paper_adaptation_updates": [
    [],
    [],
    [],
    []
   ],
   "gates": {
    "rhat_log_sigma2": true,
    "bulk_ess_log_sigma2": true,
    "tail_ess_log_sigma2": true,
    "rhat_z_last": true,
    "bulk_ess_z_last": true,
    "tail_ess_z_last": true,
    "rhat_x_last": true,
    "bulk_ess_x_last": true,
    "tail_ess_x_last": true,
    "rhat_mu_last": true,
    "bulk_ess_mu_last": true,
    "tail_ess_mu_last": true,
    "divergences": true,
    "invalid_evaluations": true,
    "refinement_exhaustions": false,
    "maximum_depth_rate": true
   },
   "all_gates_passed": false,
   "ess_per_call": {
    "log_sigma2": 0.00013458763239046817,
    "z_last": 0.00011021671116410684,
    "x_last": 0.000247142096563102,
    "mu_last": 0.00021025272688419093
   },
   "ess_per_second": {
    "log_sigma2": 56.80794872334912,
    "z_last
```
