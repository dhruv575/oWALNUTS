# Bounded-prior historical confirmation

Pre-acquisition implementation. Statistical rules and complete calendar are in
`../amm_accounting_v1/CONFIRMATION-ANALYSIS-PROTOCOL.md` and
`../amm_accounting_v1/confirmation_calendar.py`. No holdout outcomes have been
accessed during this preparation.

The collector is a reviewed copy of the prior fixed-grid collector, with only
the dates and day/bar counts changed: August 26 through October 31, 2025,
67 daily requests and 3,216 half-hour bars. Four offline fixture tests pass,
covering exact grids/timing, failure preservation, forbidden draft networking,
and HTTP/byte-cap rejection. A diff review confirmed no other behavioral change.

The AWS audit inspected 747 seed-named JSON inventories and found no explicit
scalar collision with the proposed 48,806 reserved integers. Its scope excludes
unrecorded seeds and opaque engine-internal derivations. Local audit and final
source freeze remain required; no sampling is admitted by this README.

The confirmation worker preserves the reviewed sampler and analysis settings,
maps all 3,050 calendar cells to their causal fixture and reserved seed, and
records unavailable baseline scores without replacing them. Two AWS unit tests
passed: the full calendar mapping and a forced first-method resource failure
that still attempts the second method and preserves the failure. These are
orchestration tests, not a confirmation sampling run. The temporary test layout
initially lacked its predictive-density module path; adding the read-only
dependency link fixed that import without changing campaign sources.

The bounded supervisor defines 255 batches: 254 twelve-cell batches and one
two-cell batch. Three tests pass locally and on AWS for exact denominator
coverage, retained failed jobs, and archive-plan/process-drain admission gates.
Each launch checks frozen source and runtime hashes/versions, sixteen-core
affinity and 3.5 GiB free disk. Limits remain 900 seconds/5 GiB/192 MiB per cell
and 2,760 seconds/22 GiB/2.5 GiB per batch. Archive verification must bind the
previous PLAN.json before advancement. Full source admission and archival
automation are still pending; these tests do not authorize a sampling launch.

`archive_batch.py` now supplies the archive handoff. It packages only drained
batches, verifies stored member bytes against a manifest, and binds the resulting
archive to PLAN.json. Admission requires matching upload/restore hash, byte count,
bucket, key and exact version, plus verified restoration and AES256 encryption.
Reclamation rechecks every raw NPZ hash before deleting anything and preserves
batch control records. Four archive tests pass locally; the combined seven
archive/supervisor tests pass on AWS. Test receipts are simulated binding fixtures,
not claims of S3 verification. Production transport uses the previously exercised
presigned transfer helper and real exact-version streaming verification.
