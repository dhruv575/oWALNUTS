# Repeated-fit controller validation

`persistent_comparison_plan.py` prepares and freezes a four-process, twelve-fit
development comparison. Each process fits A/B/A with fresh adaptation and fixed
immutable fixtures. A and B are the earliest eligible scheduled market origins
168 and 216 with different training observation counts. Forecast eligibility
uses known features and current anchors, never future scoring availability.

The controller reconstructs anchored prices from archived trades, verifies exact
fixtures and starts, and audits fourteen distinct streams: six sampler seeds,
six prediction seeds and two fixture-initialization seeds. Fixture starts are
then reused deterministically across paired arms and A repeats. It validates
every tier's full diagnostic family, first-pass stopping, continuation counters,
adaptation invariance and hardware containment. All twelve intended fits remain
in the record after malformed output, timeouts or provenance failures.

Individual valid fits remain visible when a clean nonzero cohort exit reflects
another fit's precision failure. Full-cohort timing ratios require both matched
cohorts to succeed. The timing report binds per-fit costs to saved report hashes,
separates first and later fit costs, retains process overhead and never imputes
missing timings. Reported costs must be finite and consistent with final writes.

## Validation evidence

On integrated main, 45 focused controller tests passed in 0.33 seconds. They
cover plan/seed mutation, archive reconstruction, fixture shape and missingness,
hardware failures, twelve-fit accounting, adaptation/transport proofs, mixed
successful/failed cohorts, and timing tampering.

A separate actual T128/G4 compatibility smoke ran three A/B/A fits for each
backend with four chains, 1,000 warmup and 1,000 retained draws. All six saved
reports passed transport, fresh-adaptation and continuation checks. All six
correctly failed the production stopping contract because the smoke stopped
before the full cap without meeting precision. This is not a benchmark or
calibration result; its synthetic masked fixtures are not market replay data.

The first smoke harness passed in-memory NumPy arrays to a validator designed
for serialized JSON and recorded an ambiguous-array-comparison failure on the
public reports. That failure is retained. Revalidating the existing saved JSON
passed all six reports without resampling. The archived replay script was also
run from main against the original local evidence and returned six passing
proofs. Subsequent controller accounting and seed-audit fixes have focused-test
coverage; they are not misrepresented as the exact source of the original smoke.

## Archive

`artifacts/persistent-controller-compatibility-v1` contains original failure and
corrected validation results, exact smoke sources, the exact serialized-validator
controller, an executable revalidation script and provenance, and compact reports.
Six raw arrays remain under the matching isolated-worktree artifact directory;
`raw-manifest.json` binds their sizes and SHA-256 hashes. To replay elsewhere,
unpack `compact-reports.zip` and restore the manifested raw files before invoking
`revalidate_serialized.py` on that evidence directory.

No production repeated-fit comparison has been frozen or launched yet. A fresh
seed audit, preparation of the actual anchored A/B fixtures and independent
prefreeze review remain required before its timing results can be interpreted.
