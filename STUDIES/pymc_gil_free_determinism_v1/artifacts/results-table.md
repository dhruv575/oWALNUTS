# WP86 results

Seed 8686001; 4 chains x 1,000/1,000; pinned to cores 4-7, co-tenanted.

| arm | model | ok | D2 cold | D2 warm | draws = same fn (cold/warm) | grad-diff processes (cold/warm) | max ulp grad / logp | gil_free hashes (all; cold/warm) | same-fn hashes | t1 = t4 (cold/warm) | = WP83 control (cold/warm) | cfunc asm variants (cold/warm) | vfmadd (cold/warm) | inner cache hits (cold/warm) | gf us/call |
|---|---|---:|---:|---:|---|---|---|---|---:|---|---|---|---|---|---:|
| A | ar1 | 10/10 | 5/5 | 5/5 | 5, 5 | 0, 0 | 0 / 0 | 2; 1/1 | 2 | — | 5, 5 | 1/1 | [None] / [None] | ['{}'] / ['{"(UniTuple(Array(float64, 1, \'C\', False, aligned=True), 1),)": 1}'] | 2.23 |
| A | data_dims_det | 10/10 | 5/5 | 5/5 | 5, 5 | 0, 0 | 0 / 0 | 2; 1/1 | 2 | — | 0, 0 | 1/1 | [None] / [None] | ['{}'] / ['{"(UniTuple(Array(float64, 1, \'C\', False, aligned=True), 1),)": 1}'] | 1.78 |
| A | eight | 10/10 | 5/5 | 5/5 | 5, 5 | 0, 0 | 0 / 0 | 1; 1/1 | 1 | — | 5, 5 | 1/1 | [None] / [None] | ['{}'] / ['{"(UniTuple(Array(float64, 1, \'C\', False, aligned=True), 1),)": 1}'] | 1.28 |
| A | logistic | 10/10 | 5/5 | 5/5 | 5, 5 | 0, 0 | 0 / 0 | 1; 1/1 | 1 | — | 5, 5 | 1/1 | [None] / [None] | ['{}'] / ['{"(UniTuple(Array(float64, 1, \'C\', False, aligned=True), 1),)": 1}'] | 11.67 |
| A | simplex_bounded | 10/10 | 5/5 | 5/5 | 5, 5 | 0, 0 | 0 / 0 | 2; 1/1 | 2 | — | 5, 5 | 1/1 | [None] / [None] | ['{}'] / ['{"(UniTuple(Array(float64, 1, \'C\', False, aligned=True), 1),)": 1}'] | 4.84 |
| B | ar1 | 10/10 | 5/5 | 5/5 | 5, 5 | 0, 0 | 0 / 0 | 1; 1/1 | 1 | — | — | 1/1 | [None] / [None] | ['{}'] / ['{"(UniTuple(Array(float64, 1, \'C\', False, aligned=True), 1),)": 1}'] | 2.27 |
| B | data_dims_det | 10/10 | 5/5 | 5/5 | 5, 5 | 0, 0 | 0 / 0 | 1; 1/1 | 1 | — | — | 1/1 | [None] / [None] | ['{}'] / ['{"(UniTuple(Array(float64, 1, \'C\', False, aligned=True), 1),)": 1}'] | 1.79 |
| B | eight | 10/10 | 5/5 | 5/5 | 5, 5 | 0, 0 | 0 / 0 | 1; 1/1 | 1 | — | — | 1/1 | [None] / [None] | ['{}'] / ['{"(UniTuple(Array(float64, 1, \'C\', False, aligned=True), 1),)": 1}'] | 1.29 |
| B | logistic | 10/10 | 5/5 | 5/5 | 5, 5 | 0, 0 | 0 / 0 | 1; 1/1 | 1 | — | — | 1/1 | [None] / [None] | ['{}'] / ['{"(UniTuple(Array(float64, 1, \'C\', False, aligned=True), 1),)": 1}'] | 11.72 |
| B | simplex_bounded | 10/10 | 5/5 | 5/5 | 5, 5 | 0, 0 | 0 / 0 | 1; 1/1 | 1 | — | — | 1/1 | [None] / [None] | ['{}'] / ['{"(UniTuple(Array(float64, 1, \'C\', False, aligned=True), 1),)": 1}'] | 4.83 |
| C | ar1 | 10/10 | 5/5 | 5/5 | 5, 5 | 0, 0 | 0 / 0 | 2; 1/1 | 2 | — | — | 1/1 | [None] / [None] | ['{}'] / ['{"(UniTuple(Array(float64, 1, \'C\', False, aligned=True), 1),)": 1}'] | 2.24 |
| C | data_dims_det | 10/10 | 5/5 | 5/5 | 5, 5 | 0, 0 | 0 / 0 | 2; 1/1 | 2 | — | — | 1/1 | [None] / [None] | ['{}'] / ['{"(UniTuple(Array(float64, 1, \'C\', False, aligned=True), 1),)": 1}'] | 1.76 |
| C | eight | 10/10 | 5/5 | 5/5 | 5, 5 | 0, 0 | 0 / 0 | 1; 1/1 | 1 | — | — | 1/1 | [None] / [None] | ['{}'] / ['{"(UniTuple(Array(float64, 1, \'C\', False, aligned=True), 1),)": 1}'] | 1.27 |
| C | logistic | 10/10 | 5/5 | 5/5 | 5, 5 | 0, 0 | 0 / 0 | 1; 1/1 | 1 | — | — | 1/1 | [None] / [None] | ['{}'] / ['{"(UniTuple(Array(float64, 1, \'C\', False, aligned=True), 1),)": 1}'] | 10.98 |
| C | simplex_bounded | 10/10 | 5/5 | 5/5 | 5, 5 | 0, 0 | 0 / 0 | 2; 1/1 | 2 | — | — | 1/1 | [None] / [None] | ['{}'] / ['{"(UniTuple(Array(float64, 1, \'C\', False, aligned=True), 1),)": 1}'] | 4.85 |
| D | ar1 | 10/10 | 5/5 | 5/5 | 5, 5 | 0, 0 | 0 / 0 | 2; 1/1 | 2 | — | — | 1/1 | [None] / [None] | ['{}'] / ['{"(UniTuple(Array(float64, 1, \'C\', False, aligned=True), 1),)": 1}'] | 2.21 |
| D | data_dims_det | 10/10 | 5/5 | 5/5 | 5, 5 | 0, 0 | 0 / 0 | 2; 1/1 | 2 | — | — | 1/1 | [None] / [None] | ['{}'] / ['{"(UniTuple(Array(float64, 1, \'C\', False, aligned=True), 1),)": 1}'] | 1.78 |
| D | eight | 10/10 | 5/5 | 5/5 | 5, 5 | 0, 0 | 0 / 0 | 1; 1/1 | 1 | — | — | 1/1 | [None] / [None] | ['{}'] / ['{"(UniTuple(Array(float64, 1, \'C\', False, aligned=True), 1),)": 1}'] | 1.28 |
| D | logistic | 10/10 | 5/5 | 5/5 | 5, 5 | 0, 0 | 0 / 0 | 1; 1/1 | 1 | — | — | 1/1 | [None] / [None] | ['{}'] / ['{"(UniTuple(Array(float64, 1, \'C\', False, aligned=True), 1),)": 1}'] | 11.70 |
| D | simplex_bounded | 10/10 | 5/5 | 5/5 | 5, 5 | 0, 0 | 0 / 0 | 2; 1/1 | 2 | — | — | 1/1 | [None] / [None] | ['{}'] / ['{"(UniTuple(Array(float64, 1, \'C\', False, aligned=True), 1),)": 1}'] | 4.84 |
| E | ar1 | 10/10 | 5/5 | 5/5 | 5, 5 | 0, 0 | 0 / 0 | 1; 1/1 | 1 | — | — | 1/1 | [None] / [None] | ['{}'] / ['{}'] | 2.08 |
| E | data_dims_det | 10/10 | 5/5 | 5/5 | 5, 5 | 0, 0 | 0 / 0 | 1; 1/1 | 1 | — | — | 1/1 | [None] / [None] | ['{}'] / ['{}'] | 1.73 |
| E | eight | 10/10 | 5/5 | 5/5 | 5, 5 | 0, 0 | 0 / 0 | 1; 1/1 | 1 | — | — | 1/1 | [None] / [None] | ['{}'] / ['{}'] | 1.22 |
| E | logistic | 10/10 | 5/5 | 5/5 | 5, 5 | 0, 0 | 0 / 0 | 1; 1/1 | 1 | — | — | 1/1 | [None] / [None] | ['{}'] / ['{}'] | 11.64 |
| E | simplex_bounded | 10/10 | 5/5 | 5/5 | 5, 5 | 0, 0 | 0 / 0 | 1; 1/1 | 1 | — | — | 1/1 | [None] / [None] | ['{}'] / ['{}'] | 4.40 |
| T | ar1 | 20/20 | 10/10 | 10/10 | 10, 10 | 0, 0 | 0 / 0 | 2; 1/1 | 2 | 10/10, 10/10 | — | 1/1 | [None] / [None] | ['{}'] / ['{"(UniTuple(Array(float64, 1, \'C\', False, aligned=True), 1),)": 1}'] | 2.22 |
| T | data_dims_det | 20/20 | 10/10 | 10/10 | 10, 10 | 0, 0 | 0 / 0 | 2; 1/1 | 2 | 10/10, 10/10 | — | 1/1 | [None] / [None] | ['{}'] / ['{"(UniTuple(Array(float64, 1, \'C\', False, aligned=True), 1),)": 1}'] | 1.77 |
| T | simplex_bounded | 20/20 | 10/10 | 10/10 | 10, 10 | 0, 0 | 0 / 0 | 2; 1/1 | 2 | 10/10, 10/10 | — | 1/1 | [None] / [None] | ['{}'] / ['{"(UniTuple(Array(float64, 1, \'C\', False, aligned=True), 1),)": 1}'] | 4.82 |

## Predictions

- H1: True
- H2: False
- H3: True
- H4: False
- H5: False
- H6: True

## Fix rule

- qualifies: {'B': True, 'C': False, 'D': False, 'E': True}
- proposed: B
- cache warming (arm A warm processes, descriptive): {'ar1': {'d2_warm': '5/5', 'warm_hashes': 1}, 'data_dims_det': {'d2_warm': '5/5', 'warm_hashes': 1}, 'eight': {'d2_warm': '5/5', 'warm_hashes': 1}, 'logistic': {'d2_warm': '5/5', 'warm_hashes': 1}, 'simplex_bounded': {'d2_warm': '5/5', 'warm_hashes': 1}}
