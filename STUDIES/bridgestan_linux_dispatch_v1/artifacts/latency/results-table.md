# WP65 part (a): gradient-call latency per dispatch path

Medians over 5 processes per (model, build); pinned to cores 4-7, co-tenanted. `us/call` = wall per call per caller; `agg us/grad` = wall / (callers x calls).

| model | build | path | execution | us/call per caller | agg us/grad | grads/s |
|---|---|---|---|---:|---:|---:|
| eight_schools-eight_schools_noncentered | nothreads | raw1 | raw fn pointer | 0.673 | 0.673 | 1,485,863 |
| eight_schools-eight_schools_noncentered | nothreads | direct1 | DirectSerialised | 0.713 | 0.713 | 1,402,262 |
| eight_schools-eight_schools_noncentered | nothreads | direct4 | DirectSerialised | 4.035 | 1.009 | 991,330 |
| eight_schools-eight_schools_noncentered | nothreads | replicated1 | ReplicatedConcurrent | 0.701 | 0.701 | 1,427,467 |
| eight_schools-eight_schools_noncentered | nothreads | replicated4 | ReplicatedConcurrent | 0.743 | 0.186 | 5,385,556 |
| eight_schools-eight_schools_noncentered | threads | raw1 | raw fn pointer | 0.818 | 0.818 | 1,223,056 |
| eight_schools-eight_schools_noncentered | threads | direct1 | DirectConcurrent | 0.814 | 0.814 | 1,227,906 |
| eight_schools-eight_schools_noncentered | threads | direct4 | DirectConcurrent | 0.924 | 0.231 | 4,327,228 |
| eight_schools-eight_schools_noncentered | threads | replicated1 | ReplicatedConcurrent | 0.819 | 0.819 | 1,221,402 |
| eight_schools-eight_schools_noncentered | threads | replicated4 | ReplicatedConcurrent | 0.851 | 0.213 | 4,702,452 |
| arK-arK | nothreads | raw1 | raw fn pointer | 20.482 | 20.482 | 48,824 |
| arK-arK | nothreads | direct1 | DirectSerialised | 20.061 | 20.061 | 49,847 |
| arK-arK | nothreads | direct4 | DirectSerialised | 83.201 | 20.800 | 48,076 |
| arK-arK | nothreads | replicated1 | ReplicatedConcurrent | 20.004 | 20.004 | 49,990 |
| arK-arK | nothreads | replicated4 | ReplicatedConcurrent | 20.493 | 5.123 | 195,184 |
| arK-arK | threads | raw1 | raw fn pointer | 32.195 | 32.195 | 31,061 |
| arK-arK | threads | direct1 | DirectConcurrent | 32.184 | 32.184 | 31,072 |
| arK-arK | threads | direct4 | DirectConcurrent | 32.709 | 8.177 | 122,289 |
| arK-arK | threads | replicated1 | ReplicatedConcurrent | 32.516 | 32.516 | 30,754 |
| arK-arK | threads | replicated4 | ReplicatedConcurrent | 32.622 | 8.155 | 122,618 |
| diamonds-diamonds | nothreads | raw1 | raw fn pointer | 38.495 | 38.495 | 25,977 |
| diamonds-diamonds | nothreads | direct1 | DirectSerialised | 38.468 | 38.468 | 25,995 |
| diamonds-diamonds | nothreads | direct4 | DirectSerialised | 159.656 | 39.914 | 25,054 |
| diamonds-diamonds | nothreads | replicated1 | ReplicatedConcurrent | 38.812 | 38.812 | 25,766 |
| diamonds-diamonds | nothreads | replicated4 | ReplicatedConcurrent | 40.082 | 10.020 | 99,796 |
| diamonds-diamonds | threads | raw1 | raw fn pointer | 38.820 | 38.820 | 25,760 |
| diamonds-diamonds | threads | direct1 | DirectConcurrent | 38.513 | 38.513 | 25,965 |
| diamonds-diamonds | threads | direct4 | DirectConcurrent | 39.602 | 9.901 | 101,004 |
| diamonds-diamonds | threads | replicated1 | ReplicatedConcurrent | 39.256 | 39.256 | 25,474 |
| diamonds-diamonds | threads | replicated4 | ReplicatedConcurrent | 39.484 | 9.871 | 101,308 |

## Ratios

| ratio | eight_schools-eight_schools_noncentered | arK-arK | diamonds-diamonds |
|---|---:|---:|---:|
| A1_threads_over_nothreads_raw1_latency | 1.215 | 1.572 | 1.008 |
| A2_replicated4_over_direct4_throughput_nothreads | 5.433 | 4.060 | 3.983 |
| A3_threads_direct4_over_nothreads_direct4_throughput | 4.365 | 2.544 | 4.031 |
| A4_direct1_over_raw1_latency_nothreads | 1.060 | 0.979 | 0.999 |
| A4_direct1_over_raw1_latency_threads | 0.996 | 1.000 | 0.992 |
| A4_replicated1_over_direct1_latency_nothreads | 0.982 | 0.997 | 1.009 |
| A4_replicated1_over_direct1_latency_threads | 1.005 | 1.010 | 1.019 |
| reported_replicated4_over_replicated1_per_caller_latency_nothreads | 1.060 | 1.024 | 1.033 |
| reported_threads_replicated4_over_threads_direct4_throughput | 1.087 | 1.003 | 1.003 |
| reported_direct4_over_direct1_per_caller_latency_nothreads | 5.658 | 4.147 | 4.150 |

## Preregistered predictions

| prediction | statement | held |
|---|---|---|
| A1 | STAN_THREADS costs little on Linux: raw1 latency threads / nothreads <= 1.25 on each of the three models (Windows mingw: 9-16x). Point predictions: eight schools 1.15, arK 1.05, diamonds 1.05. | False |
| A2 | Replicas scale: nothreads replicated4 / direct4 gradient throughput >= 3.0 on each model. Point: 3.7 on each. | True |
| A3 | One STAN_THREADS module scales: threads direct4 / nothreads direct4 throughput >= 2.5 on each model. Point: 3.4. | True |
| A4 | The Rust wrapper and the replica dispatch are cheap: direct1 / raw1 and replicated1 / direct1 latency <= 1.15 on every model and build. Point: <= 1.05. | True |
