# Fixed bounded-scale multi-observation panel

All nine planned fits completed. Every T=250 case passed both methods' full
coordinate diagnostics: all-distinct and exactly-two-zero fixtures, each at
caps .5, 1 and 2. NUTS had zero retained divergences and depth-limit hits in
those six fits. Maximum absolute coordinate mean differences ranged from
2.744 to 3.587 combined MCSEs, with no coordinate above four. These are
descriptive implementation comparisons, not simultaneous confidence bounds.

All three T=12 all-zero cases failed to establish an independent reference.
Slice failed 14 of 15 coordinates at each cap. NUTS passed at cap .5, but failed
all 15 at caps 1 and 2, with respectively 13,342 and 11,405 depth-limit hits.
There were no retained NUTS divergences. Cap 2 had a maximum mean discrepancy
of 12.514 combined MCSEs, but poor mixing prevents interpreting that number as
a calibrated discrepancy test. All original failures and traces are preserved.

The supervised campaign took 156.397 seconds, with peak RSS 7,955,509,248 bytes
and output 813,353,394 bytes. Up to four fits used disjoint groups of four CPUs.
All process groups drained and source bindings stayed unchanged. An earlier
SSH observation failed before the lane existed; absence of the lane and jobs
was checked before the successful single launch. No replacement seeds were run.

The full archive downloaded with the remote SHA256 intact: 809,797,266 bytes,
177 files. The verifier checked source bindings, all 36 slice arrays' shapes
and finiteness, and reproduced reported diagnostic classifications and mean
discrepancies from coordinate CSVs. NUTS raw traces are hashed and preserved;
this verifier does not independently recompute their ArviZ diagnostics.

Raw arrays and NUTS files remain in target/bounded-multi-full.tar.gz and the
remote lane; the Git evidence includes sources, reports, logs, coordinate CSVs
and a full byte/hash manifest. Exact-version S3 restore verification subsequently
passed (S3-VERIFIED.json). The redundant remote archive alone was then removed
after another SHA256 check, reclaiming 809,797,266 bytes (CLEANUP.json). The remote
raw lane and both local archive copies remain available.

The all-zero geometry audit and exact coordinate-change follow-up are described
in ../../BOUNDED-SCALE-GEOMETRY-NEXT.md. No prior cap is selected. This synthetic
panel does not establish market predictive accuracy, decision value or profit.
