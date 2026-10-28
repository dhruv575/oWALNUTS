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
