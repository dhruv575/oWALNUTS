# Pharmacokinetic ODE pilot

Completed: [conclusion](results-20261029/corrected/CONCLUSION.md),
[tables](results-20261029/corrected/REPORT.md) and
[audit](results-20261029/corrected/AUDIT.json). The public ODE sampler gate passes;
the full practical-success rule does not. Patient matched-accuracy claims are
blocked by unqualified references. Preserve both corrected and legacy evidence.

See [protocol](PROTOCOL.md), [operations](OPERATIONS.md) and the
[forecast numerical amendment](forecast_fix/AMENDMENT.md). This is a small
research pilot, not a clinical evaluation, decision-policy trial or product.

Source snapshots under `source_data` have recorded URL/SHA256 provenance. The
Stan fixture has unverified clinical origin. The observed-data check selects
Theoph subjects 1, 2 and 3 by numeric ID, trains on eight post-baseline points
and withholds the final two. Do not interpret six heldout points as validation
of a medical application. Training priors are explicit working assumptions.

## Reproduction layout

Use a Linux root with `source/`, `data/`, `prepared/`, `build/`, `packaging/`.
Copy top-level Python, adapter.cpp, model.stan and PROTOCOL.md to `source/`;
copy data snapshots and generated data to the matching root directories.
For the corrected run overlay files in `forecast_fix/` onto `source/`.
`backend.py` resolves ROOT as the parent of its source directory.
The archived ENVIRONMENT.json records exact installed versions; compiled
model and adapter binaries are archived, with source and build-command logs.

Build adapter with
`g++ -O3 -std=c++17 -shared -fPIC -pthread source/adapter.cpp -ldl -o build/adapter.so`.
Build model using BridgeStan 2.9.0's make target `<root>/build/model_model.so`,
from `<root>/build/model.stan`, without STAN_THREADS. Use one BLAS/OpenMP/MKL
thread per worker. `prepare.py` creates shared MAP/Hessian/initial points;
no heldout observation value enters preparation. Validate with
`python -m unittest test_backend` and, for corrected forecasts,
`python -m unittest test_log_forecast` (its legacy path is recorded explicitly).

Run `supervisor.py initial <absolute-run-folder>`. After terminal FINAL,
`analyze.py initial <run-folder>` writes calibration-only SELECTION.json and
audited REFERENCES.json. Freeze selection before
`supervisor.py validate <absolute-validation-folder> <absolute-SELECTION.json>`.
Then `analyze.py final <validation-folder>`. Never tune from validation results.
Resource bounds, seeds and all qualification rules are specified in protocol.

`test_analysis.py` runs with source on PYTHONPATH, outside the frozen source
tree. It verifies reference/precision gates, selection ordering and censoring.
`audit_campaign.py` independently checks snapshot hashes, observation partitions,
seed separation, selection/source freezes and every terminal resource receipt.
`check_progress.py` is read-only. `receive_archive.py` streams the complete
remote evidence and verifies each member and source freeze; no second remote
tar is needed. Raw evidence stays outside Git; compact reports/receipts belong
in Git. Preserve legacy forecast failures and the aborted path-bug attempt.
One-time model compilation is recorded separately and is not charged to each
fit's cold worker total. See [related-work context](RELATED-WORK.md) for limits
on novelty and practical-advantage claims.
