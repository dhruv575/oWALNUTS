# WP70 diagnosis (accel_gp, phase 1)

| hypothesis | statistic | value | threshold | supported |
|---|---|---|---|---|
| H1 truncation | RC-stop fraction; integration-time ratio oWALNUTS/CmdStan | 0.5511666666666667; 0.8651426126312711 | >= 0.4; <= 0.6 | False |
| H2 depth cap | maximum-depth stop fraction | 8.333333333333333e-05 | >= 0.05 | False |
| H3 adaptation | metric mismatch ratio oWALNUTS/CmdStan | 1.4270083130493763 | >= 1.5 | False |

## Reported

```
{
 "step_size_median": {
  "owalnuts": {
   "700711": 0.007903287765591068,
   "700712": 0.0073126530338849405,
   "700713": 0.007592755328154146
  },
  "cmdstan": {
   "700711": 0.00647354,
   "700712": 0.00789931,
   "700713": 0.007145885
  },
  "ratio_median": 1.0625353372121362
 },
 "mean_acceptance_statistic": {
  "owalnuts": {
   "700711": null,
   "700712": null,
   "700713": null
  },
  "cmdstan": {
   "700711": 0.9316496927844501,
   "700712": 0.8718974952019379,
   "700713": 0.9128441300038207
  },
  "ratio_median": null
 },
 "warmup_gradient_share": {
  "owalnuts": {
   "700711": 0.527371804890497,
   "700712": 0.4141774385577005,
   "700713": 0.45073563114811577
  },
  "cmdstan": {
   "700711": 0.4248744189381517,
   "700712": 0.5096430191797143,
   "700713": 0.4825894056003809
  },
  "ratio_median": 0.9339940452844455
 },
 "gradients_per_retained_transition": {
  "owalnuts": {
   "700711": 304.66925,
   "700712": 468.43075,
   "700713": 405.33225
  },
  "cmdstan": {
   "700711": 850.22425,
   "700712": 604.1605,
   "700713": 678.20525
  },
  "ratio_median": 0.5976542499486697
 },
 "integration_time_median": {
  "owalnuts": {
   "700711": 2.5212152478918686,
   "700712": 3.5517083913005263,
   "700713": 3.5633215461317285
  },
  "cmdstan": {
   "700711": 6.35437473,
   "700712": 4.1053444131,
   "700713": 3.9702120472
  },
  "ratio_median": 0.8651426126312711
 },
 "step_size_max_over_min": {
  "owalnuts": {
   "700711": 1.471944141494994,
   "700712": 1.6183575629608042,
   "700713": 1.188397511926783
  },
  "cmdstan": {
   "700711": 1.1393477592405068,
   "700712": 1.3928971151852103,
   "700713": 1.2543367812324935
  },
  "ratio_median": 1.1618643942310234
 },
 "metric_mismatch_q90_median_over_chains": {
  "owalnuts": {
   "700711": 0.24118227845441348,
   "700712": 0.25012627056638365,
   "700713": 0.25427882829785986
  },
  "cmdstan": {
   "700711": 0.18549516638101798,
   "700712": 0.17528017761290293,
   "700713": 0.17352906943656554
  },
  "ratio_median": 1.4270083130493763
 },
 "owalnuts_refined_selected_fraction": {
  "700711": 0.3867875647668394,
  "700712": 0.29788319306299416,
  "700713": 0.29753972321886213
 },
 "owalnuts_retained_refinement_level_histogram": {
  "700711": [
   2367,
   1488,
   5,
   0,
   0,
   0,
   0,
   0,
   0
  ],
  "700712": [
   2753,
   1167,
   1,
   0,
   0,
   0,
   0,
   0,
   0
  ],
  "700713": [
   2741,
   1159,
   2,
   0,
   0,
   0,
   0,
   0,
   0
  ]
 },
 "owalnuts_retained_stop_counts": {
  "700711": {
   "outer_u_turn": 1423,
   "recursive_u_turn": 64,
   "reverse_coarser_accepted": 2513
  },
  "700712": {
   "outer_u_turn": 1727,
   "recursive_u_turn": 194,
   "reverse_coarser_accepted": 2079
  },
  "700713": {
   "maximum_depth": 1,
   "outer_u_turn": 1840,
   "recursive_u_turn": 137,
   "reverse_coarser_accepted": 2022
  }
 },
 "owalnuts_integration_time_median_by_stop": {
  "700711": {
   "outer_u_turn": 3.8122879752572447,
   "recursive_u_turn": 7.617190325607752,
   "reverse_coarser_accepted": 0.7982677365020063
  },
  "700712": {
   "outer_u_turn": 3.921823009329883,
   "recursive_u_turn": 6.559672938260813,
   "reverse_coarser_accepted": 1.1518714471460327
  },
  "700713": {
   "maximum_depth": 7.520564007752755,
   "outer_u_turn": 4.003189681481397,
   "recursive_u_turn": 7.133616324251974,
   "reverse_coarser_accepted": 1.2097174603623662
  }
 },
 "owalnuts_depth_ge_10_fraction": {
  "700711": 0.02975,
  "700712": 0.25425,
  "700713": 0.1115
 },
 "cmdstan_depth_cap_fraction": {
  "700711": 0.53175,
  "700712": 0.1765,
  "700713": 0.2425
 },
 "argmin_bulk_ess": {
  "owalnuts": {
   "700711": "zgp_sigma_1[3]",
   "700712": "zgp_1[25]",
   "700713": "sdgp_1"
  },
  "cmdstan": {
   "700711": "lscale_1",
   "700712": "zgp_sigma_1[11]",
   "700713": "lscale_1"
  }
 },
 "baseline_bulk_ess_per_gradient_ratio_vs_cmdstan": 0.5670939149624147
}
```
