# Compact bank adapter validation

Eleven focused tests passed. They exercise the exact 12-endpoint family,
independent-stream and pilot-exclusion rules, full expected-fit denominator,
and rejection of incomplete or unhealthy coordinate, functional and forecast
diagnostics. Renaming a pilot fit does not evade its pinned stream exclusion.

`integrated-admission-validation-v2.json` records diagnostic admission of both
actual saved reference pilot outputs against the final integrated adapter.
The executable `validate_integrated_admission.py` accepts explicit `--study`
and `--out` paths and refuses to overwrite evidence. Raw hashes, fixture and
initialization bindings, and both 4k/8k checkpoint families are checked.

The earlier v1 result is preserved and predates the final helper refactor;
v2 is the applicable final-source evidence. Neither call constructs a bank.
Pilot draws remain prohibited by the prospective collection manifest, and
predictive-cache admission and posterior-accuracy qualification remain false.
