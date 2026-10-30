# Independent NUTS exchange mechanism test

Reuse JUMP-PROTOCOL.md's starts, whitening, step 0.05, chunk lengths, burn-in,
move schedule and limits. PyMC 5.28.2 NUTS uses explicit identity precision,
adapt_step_size=False, tune=False, max depth 12, Emax=1000. Four independent
persistent kernel objects, one per chain, with seeds 934100001 (plain) or
934100002 (jump) plus chain index * 10000; MH separate seed + 100.
Density/gradient parity and constant step/nonadaptive metric passed first.
This tests shared usefulness of exchanges, not a native-engine speed ranking.
PyMC control runs from isolated /dev/shm/population-pymc-control-env without
changing the pinned research environment. Installation log and exact versions
must be archived. Preserve exceptions and timeouts; no automatic retries.
