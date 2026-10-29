# Curvature scaling and local-error tuning

This extends the selected banana result in geometry_precision_v1 to six
all-pairs curved targets and an equal tuning budget per sampler. Read
[PROTOCOL.md](PROTOCOL.md) before interpreting results. The exact Gaussian
reparameterization is a deliberately strong control.

The archived Linux run layout has a frozen `source` directory and the pinned
Python environment recorded in ENVIRONMENT.json. Recompute from saved rows:

```sh
cd source
OPENBLAS_NUM_THREADS=1 python -m unittest test_study
OPENBLAS_NUM_THREADS=1 python analyze.py select ../calibrate-v1 ../new-selection.json
OPENBLAS_NUM_THREADS=1 python analyze.py report ../test-v1 ../new-analysis
```

Never overwrite original selections or run folders. Source hashes and process
receipts are part of each phase. Full raw double-precision draws are archived;
the committed compressed rows preserve diagnostics and costs. Calibration
selects configurations, while held-out seeds measure their performance.
Identical selected/default configurations reuse identical seeds and are not
independent replicates. Censored fits must not be assigned invented costs.

`stream_archive.py` creates the remote evidence manifest and streams a gzip
archive without a duplicate EC2 tar file. `receive_archive.py` uses a binary
SSH stream, verifies every member and executed-source hash, and checks that
held-out selection matches the frozen selection hash before exporting results.
