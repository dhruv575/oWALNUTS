# Activity-based acquisition integration

The acquisition controller now accepts an explicit `activity_selection` protocol.
It validates prospective thresholds before requests, completes first-day discovery,
then ranks by fresh-anchor bins, active feature bins, trade count, and instrument
name. Metadata eligibility is applied in that order until four contracts qualify.
Insufficient activity fails without weakening thresholds or reverting to volume.
The legacy volume-selection path remains available when this option is absent.

The collector archives ranking, metadata exclusions and unqueried candidates.
Selection is available only after the preperiod plus its 60-second lag. It binds
both collector and ranking-helper sources and snapshots them before discovery,
including when discovery fails. This is retrospective data construction; these
records do not establish historical receipt times or feed completeness.

Validation on the integrated main files:

```
target/python-workflow-env/Scripts/python.exe -m pytest \
  STUDIES/options_flow_v1/test_activity_acquisition_integration.py \
  STUDIES/options_flow_v1/test_active_contract_selection.py \
  STUDIES/options_flow_v1/test_acquire_deribit_panel.py -q
```

27 tests passed in 0.17 seconds. Tests use mocked acquisition, covering selection,
metadata replacement, threshold failure, unchanged legacy policy, helper-source
mutation and source preservation before a discovery failure. An initial isolated
test used a mocked year beyond ZIP's supported range; the mock was corrected to
the protocol end plus 72 hours without changing collector behavior for the test.

No new network acquisition has run. Production activity thresholds and the new
historical window require a concrete prospective protocol before collection.
