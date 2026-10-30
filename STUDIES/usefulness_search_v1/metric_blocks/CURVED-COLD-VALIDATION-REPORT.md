# Tuned curved cold validation

Competitive efficiency gate passed: False. Promotion established: False. Ratios above one favor direct recycled WAL.

| Family | Control | MSE ratio | Single-fit adjusted ratio (range) | Calibration-amortized ratio (range) |
|---|---|---:|---|---|
| mean | direct_wal_ordinary | 1.099 | 0.994 (0.970-1.018) | 0.993 (0.972-1.013) |
| mean | direct_native_ordinary | 1.238 | 0.318 (0.218-0.492) | 0.484 (0.335-0.743) |
| mean | direct_native_recycled | 1.108 | 0.405 (0.269-0.647) | 0.577 (0.385-0.915) |
| mean | latent_wal_ordinary | 0.407 | 0.026 (0.023-0.030) | 0.023 (0.021-0.026) |
| mean | latent_wal_recycled | 0.242 | 0.017 (0.015-0.020) | 0.015 (0.014-0.017) |
| mean | latent_native_ordinary | 0.443 | 0.014 (0.012-0.016) | 0.023 (0.021-0.026) |
| mean | latent_native_recycled | 0.253 | 0.012 (0.010-0.013) | 0.017 (0.015-0.019) |
| mean | exact | 0.286 | 0.003 (0.003-0.004) | 0.001 (0.001-0.002) |
| second_moment | direct_wal_ordinary | 1.087 | 0.984 (0.955-1.015) | 0.983 (0.957-1.010) |
| second_moment | direct_native_ordinary | 5.573 | 1.431 (0.192-3.842) | 2.178 (0.295-5.804) |
| second_moment | direct_native_recycled | 5.462 | 1.995 (0.246-5.404) | 2.845 (0.354-7.649) |
| second_moment | latent_wal_ordinary | 0.385 | 0.025 (0.020-0.030) | 0.022 (0.018-0.027) |
| second_moment | latent_wal_recycled | 0.204 | 0.015 (0.012-0.018) | 0.013 (0.011-0.016) |
| second_moment | latent_native_ordinary | 0.477 | 0.015 (0.012-0.019) | 0.025 (0.021-0.030) |
| second_moment | latent_native_recycled | 0.244 | 0.011 (0.009-0.014) | 0.016 (0.013-0.020) |
| second_moment | exact | 0.193 | 0.002 (0.002-0.003) | 0.001 (0.001-0.001) |
| below_zero | direct_wal_ordinary | 1.277 | 1.156 (1.105-1.212) | 1.155 (1.107-1.205) |
| below_zero | direct_native_ordinary | 1.279 | 0.328 (0.282-0.384) | 0.500 (0.432-0.579) |
| below_zero | direct_native_recycled | 0.943 | 0.344 (0.295-0.405) | 0.491 (0.423-0.573) |
| below_zero | latent_wal_ordinary | 0.736 | 0.047 (0.041-0.053) | 0.042 (0.038-0.047) |
| below_zero | latent_wal_recycled | 0.371 | 0.027 (0.023-0.030) | 0.024 (0.021-0.026) |
| below_zero | latent_native_ordinary | 0.742 | 0.024 (0.020-0.027) | 0.039 (0.034-0.045) |
| below_zero | latent_native_recycled | 0.363 | 0.017 (0.014-0.019) | 0.024 (0.021-0.028) |
| below_zero | exact | 0.604 | 0.007 (0.006-0.008) | 0.003 (0.002-0.003) |
| below_minus_two | direct_wal_ordinary | 1.362 | 1.232 (1.175-1.296) | 1.231 (1.177-1.289) |
| below_minus_two | direct_native_ordinary | 1.333 | 0.342 (0.290-0.403) | 0.521 (0.446-0.608) |
| below_minus_two | direct_native_recycled | 0.932 | 0.341 (0.288-0.403) | 0.486 (0.414-0.571) |
| below_minus_two | latent_wal_ordinary | 0.804 | 0.051 (0.044-0.060) | 0.046 (0.040-0.053) |
| below_minus_two | latent_wal_recycled | 0.381 | 0.027 (0.023-0.032) | 0.024 (0.021-0.028) |
| below_minus_two | latent_native_ordinary | 0.823 | 0.026 (0.022-0.031) | 0.043 (0.038-0.050) |
| below_minus_two | latent_native_recycled | 0.389 | 0.018 (0.015-0.021) | 0.026 (0.022-0.030) |
| below_minus_two | exact | 0.461 | 0.006 (0.005-0.007) | 0.002 (0.002-0.003) |
