# Anchored as-of replay

The return target is log(future eligible trade price) minus log(known reference trade price). A missing reference makes this target unavailable. Forecast eligibility uses current feature availability AND a known positive reference price no more than30minutes old at the feature cutoff. It never uses future trade arrival or labels.

The fixed eight-origin schedule remains unchanged. Every origin retains four scheduled groups and four algorithm/ablation cells. Origins with no eligible forecast groups remain `no_forecast_eligible`, unattempted and unsuccessful. Their worker cost is zero; measured controller overhead remains in total elapsed cost. Attempted fits gate all140canonical coordinates and14physical functionals, plus the variable eligible forecast family.

Preparation uses explicit Python functions; there is no implicit launch:

```python
panel = load_verified_panel(archive, expected_manifest_sha256=pinned_manifest,
                            expected_protocol_sha256=pinned_protocol)
derived = attach_archived_anchors(panel, archive)
# Persist derived to a NEW panel file, leaving archived inputs unchanged.
# asof_rolling_protocol.prepare(..., panel_path=new_panel, ...) creates a draft.
# asof_rolling_execute.freeze(directory) is a separate explicit action.
# asof_rolling_execute.execute(directory / "plan.json") launches the frozen plan.
```

`attach_archived_anchors` resolves the already-selected reference identity to an instrument/trade ID/timestamp in hash-bound archived trade files. It adds its positive native-quote price to a derived copy. It does not select a new reference using future observations. The inference fixture contains current anchors, known flow, matured historical outcomes, explicit masks, and no future labels. Delayed scoring remains a separate identity-bound join after immutable completed reports.

Read-only inspection of the archived panel found five eligible origin/group cells:168/0,216/1,264/1,288/1,312/0. Only168/0 and288/1 have eligible delayed labels. Origins144,192,240 have no eligible forecasts. All32scheduled origin/group cells remain in reporting. This is sparse event-time-plus-assumed-lag replay, not receipt-time verification, a coverage qualification, or evidence of profitable flow information. Historical scenario outputs are unchanged.

Validation: initial focused run had70passes and one actual-reference failure because a concurrent isolated study edit triggered the existing source-integrity guard. That failure was not bypassed. Under a coordinated source hold, both actual worker metadata tests and the executor/cost regressions passed (26tests,13.86s). Earlier full non-worker anchor suite passed68tests; the subsequently added reporter variable-family test also passed in the70-pass run. Read-only real-panel smoke verified five eligible forecasts, two labels, the three empty origins, all future inference labels absent, and unchanged original panel digest. No rolling campaign was launched.
