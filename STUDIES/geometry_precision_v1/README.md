# Geometry precision benchmark

See [results](results-20261029/REPORT.md), [original protocol](PROTOCOL.md), and
[post-screen native follow-up](NATIVE-FOLLOWUP.md). The remote archive preserves
the exact executed layout and sources; current native_check.py is the corrected
adapter. Never overwrite an existing run directory.

In the archived Linux layout, using the pinned research environment:

```sh
cd analysis-source
OPENBLAS_NUM_THREADS=1 PYTHONPATH=../source:../supplement-source:../native-source-v2 python -m unittest test_targets test_supplements test_analysis test_native
python analyze.py .. ../new-analysis
python analyze_native.py ../native-v2 ../new-native-analysis
```

These commands recompute diagnostics summaries from saved result rows; raw
retained draws are also archived for independent reanalysis. Runtime package
versions are in results-20261029/SUMMARY.json. Consult supervisors for the
resource-constrained execution commands, source freezes, and seed schedules.
The warm experiment has six updates per stream and three methods; it is not
a warm-NUTS comparison. Native-v1 is intentionally retained as invalid adapter
evidence; native-v2 repeats its seeds after the documented correction.

Verify the full local raw archive without extracting filesystem paths:

```sh
python verify_archive.py ../../target/geometry-precision-evidence-v1.tar.gz 40897ff2a2fa8b7de1fd3e54fb752f4491c57f354edb68dba681da9fc32befb6
```

The smaller gzipped row files committed beside the report contain metrics and
costs; the raw archive contains draws, process receipts, failures, and sources.
