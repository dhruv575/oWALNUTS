# Fresh funnel error guard

| Target | Arm | Seed | Qualified | Divergences | Depth caps | Failed moments | Calls |
|---|---|---|---|---|---|---|---|
| noncentered | default | 941000001 | True | 0 | 0 | - | 592023 |
| noncentered | permissive | 941000001 | True | 0 | 0 | - | 592273 |
| centered | default | 941000001 | False | 0 | 5 | U0_mean,U0_lower,omega_below_minus5,omega_below_minus6 | 3495169 |
| centered | permissive | 941000001 | False | 33 | 7 | U0_mean,U7_mean,U0_lower,U0_upper,joint_lower_median,centered_product,omega_below_minus5,omega_below_minus6 | 2953723 |
| noncentered | default | 941000002 | True | 0 | 0 | - | 596576 |
| noncentered | permissive | 941000002 | True | 0 | 0 | - | 585339 |
| centered | default | 941000002 | False | 0 | 21 | U0_mean,U0_lower,omega_below_minus5,omega_below_minus6 | 3909851 |
| centered | permissive | 941000002 | False | 0 | 76 | U0_mean,U0_lower,U0_upper,joint_lower_median,omega_below_minus5,omega_below_minus6 | 2363168 |
| noncentered | default | 941000003 | True | 0 | 0 | - | 591610 |
| noncentered | permissive | 941000003 | True | 0 | 0 | - | 583412 |
| centered | default | 941000003 | False | 1 | 9 | U0_mean,U0_lower,joint_lower_median,omega_below_minus5 | 4225046 |
| centered | permissive | 941000003 | False | 3 | 16 | U0_mean,U8_mean,U9_mean,U0_lower,U1_upper,U2_lower,U2_upper,joint_lower_median,centered_product,omega_below_minus5,omega_below_minus6 | 2307025 |
| noncentered | default | 941000004 | True | 0 | 0 | - | 584419 |
| noncentered | permissive | 941000004 | True | 0 | 0 | - | 585877 |
| centered | default | 941000004 | False | 0 | 5 | U0_mean,U0_lower,omega_below_minus5 | 3357896 |
| centered | permissive | 941000004 | False | 0 | 8 | U0_mean,U0_lower,U0_upper,joint_lower_median,omega_below_minus5,omega_below_minus6 | 2258865 |

Permissive promotion guard passed: False
All easy controls qualified: True

All raw evidence is preserved. This guard cannot establish general correctness, novelty, or application value.
