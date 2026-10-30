# Independent recycled baseline elimination screen

Primary gate passed: False. Ratios above one favor recycled WAL. WAL receives uncharged fixed geometry while native pays for 1,000 warmup draws; positive results require a fair cold-start study.

| Target | Family | Control | MSE ratio | Cost ratio | Adjusted ratio | Descriptive range |
|---|---|---|---:|---:|---:|---|
| noncentered | mean | wal_ordinary | 1.195 | 0.903 | 1.079 | 0.996-1.179 |
| noncentered | mean | diag_ordinary | 0.958 | 0.463 | 0.444 | 0.351-0.566 |
| noncentered | mean | diag_recycled | 0.419 | 0.602 | 0.252 | 0.202-0.317 |
| noncentered | mean | low_rank_ordinary | 0.829 | 1.452 | 1.203 | 0.974-1.505 |
| noncentered | mean | low_rank_recycled | 0.386 | 1.594 | 0.616 | 0.492-0.783 |
| noncentered | second_moment | wal_ordinary | 1.677 | 0.903 | 1.514 | 1.399-1.640 |
| noncentered | second_moment | diag_ordinary | 1.190 | 0.463 | 0.551 | 0.458-0.665 |
| noncentered | second_moment | diag_recycled | 0.617 | 0.602 | 0.372 | 0.315-0.437 |
| noncentered | second_moment | low_rank_ordinary | 1.195 | 1.452 | 1.735 | 1.490-2.021 |
| noncentered | second_moment | low_rank_recycled | 0.677 | 1.594 | 1.079 | 0.925-1.263 |
| noncentered | below_zero | wal_ordinary | 1.394 | 0.903 | 1.258 | 1.128-1.412 |
| noncentered | below_zero | diag_ordinary | 1.209 | 0.463 | 0.560 | 0.453-0.700 |
| noncentered | below_zero | diag_recycled | 0.521 | 0.602 | 0.314 | 0.263-0.378 |
| noncentered | below_zero | low_rank_ordinary | 1.179 | 1.452 | 1.711 | 1.398-2.101 |
| noncentered | below_zero | low_rank_recycled | 0.507 | 1.594 | 0.808 | 0.668-0.984 |
| noncentered | below_minus_two | wal_ordinary | 1.316 | 0.903 | 1.188 | 1.098-1.299 |
| noncentered | below_minus_two | diag_ordinary | 0.626 | 0.463 | 0.290 | 0.200-0.432 |
| noncentered | below_minus_two | diag_recycled | 0.284 | 0.602 | 0.171 | 0.126-0.243 |
| noncentered | below_minus_two | low_rank_ordinary | 0.581 | 1.452 | 0.844 | 0.616-1.197 |
| noncentered | below_minus_two | low_rank_recycled | 0.255 | 1.594 | 0.406 | 0.302-0.562 |
| analytic_rotated_gaussian | mean | wal_ordinary | 1.212 | 0.884 | 1.072 | 0.950-1.222 |
| analytic_rotated_gaussian | mean | diag_ordinary | 1.135 | 0.485 | 0.550 | 0.369-0.829 |
| analytic_rotated_gaussian | mean | diag_recycled | 0.704 | 0.569 | 0.401 | 0.258-0.619 |
| analytic_rotated_gaussian | mean | low_rank_ordinary | 0.921 | 0.696 | 0.641 | 0.452-0.896 |
| analytic_rotated_gaussian | mean | low_rank_recycled | 0.579 | 0.772 | 0.447 | 0.318-0.623 |
| analytic_rotated_gaussian | second_moment | wal_ordinary | 1.335 | 0.884 | 1.180 | 1.033-1.337 |
| analytic_rotated_gaussian | second_moment | diag_ordinary | 0.845 | 0.485 | 0.410 | 0.277-0.598 |
| analytic_rotated_gaussian | second_moment | diag_recycled | 0.541 | 0.569 | 0.308 | 0.205-0.451 |
| analytic_rotated_gaussian | second_moment | low_rank_ordinary | 0.909 | 0.696 | 0.632 | 0.469-0.832 |
| analytic_rotated_gaussian | second_moment | low_rank_recycled | 0.559 | 0.772 | 0.431 | 0.319-0.574 |
| analytic_rotated_gaussian | below_zero | wal_ordinary | 1.256 | 0.884 | 1.111 | 0.947-1.317 |
| analytic_rotated_gaussian | below_zero | diag_ordinary | 1.429 | 0.485 | 0.693 | 0.476-1.024 |
| analytic_rotated_gaussian | below_zero | diag_recycled | 0.738 | 0.569 | 0.420 | 0.281-0.627 |
| analytic_rotated_gaussian | below_zero | low_rank_ordinary | 1.043 | 0.696 | 0.725 | 0.495-1.065 |
| analytic_rotated_gaussian | below_zero | low_rank_recycled | 0.613 | 0.772 | 0.473 | 0.335-0.669 |
| analytic_rotated_gaussian | below_minus_two | wal_ordinary | 1.335 | 0.884 | 1.180 | 0.979-1.408 |
| analytic_rotated_gaussian | below_minus_two | diag_ordinary | 1.005 | 0.485 | 0.487 | 0.343-0.689 |
| analytic_rotated_gaussian | below_minus_two | diag_recycled | 0.623 | 0.569 | 0.355 | 0.243-0.517 |
| analytic_rotated_gaussian | below_minus_two | low_rank_ordinary | 1.051 | 0.696 | 0.731 | 0.486-1.094 |
| analytic_rotated_gaussian | below_minus_two | low_rank_recycled | 0.586 | 0.772 | 0.452 | 0.286-0.717 |
