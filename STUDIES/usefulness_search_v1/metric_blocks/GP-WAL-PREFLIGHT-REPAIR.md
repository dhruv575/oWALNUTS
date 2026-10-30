# Preflight/build repairs

The isolated manifests initially omitted the existing research feature needed by with_dense_auto_select; enable that feature in both pristine and tuned drivers, preserving original manifests/build log. No kernel change.

The first100-warmup preflight is rejected before sampling because the existing automatic selector requests a slow-window index beyond that shortened schedule. Preserve that failure and repeat all six preflight cells at the actual planned1100 warmup, still100 retained draws. This checks the configuration that will be sampled and does not alter the calibration budget, settings, seeds or selection rule. Use new attempt directory gp_wal_driver_test02. Only launch calibration after all exact parity checks pass.
