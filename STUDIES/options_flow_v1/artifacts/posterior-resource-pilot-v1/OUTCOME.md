# Demanding posterior resource pilot: partial workflow completion

All four intended fits were attempted. The controller recorded 834.8505353
seconds. Both reference fits completed the entire resource workflow; both public
fits completed sampling but failed the subsequent adapter check. No fit was
replaced or retried.

| Fit | Full attempted process cost | Resource outcome |
| --- | ---: | --- |
| 0, public | 146.2645 s | Adapter metadata failure after sampling |
| 1, reference | 282.0602 s | Completed |
| 2, reference | 267.9956 s | Completed |
| 3, public | 138.5269 s | Adapter metadata failure after sampling |

Both reference fits passed the full health and endpoint-precision checks at
4,000 and 8,000 draws, and their predictive CDF calculations reported quadrature
convergence. Their peak process committed memory was approximately 6.61 and
6.60 GB, below the fixed 8-GiB cap. These are resource and diagnostic findings,
not proof of posterior endpoint accuracy or bootstrap coverage.

The public adapter selected package bindings by filename alone, incorrectly
requiring the new `posterior_resource/__init__.py` in the legacy sampler's
report. The sampler itself does not report that outer package. Read-only
comparison identified this extra requirement as the sole binding discrepancy;
the actual sampler source, attested runtime package and fixture hashes matched.
Both sampler return codes were zero, but their original resource outcomes stay
failed because extraction and separate checkpoint analysis were not completed.

The public and reference process costs cover different completed work, so this
pilot does not support a full-workflow speed ratio. Posthoc analysis of saved
public draws may recover resource and diagnostic information without new
sampling. Any such analysis must retain the original failures, separately
measure its additional costs, and use fresh output paths and archived sources.

The independent terminal audit passed all 40 checks. Its exact auditor, executed
study and package sources, and provenance are archived in `independent-terminal-*`.
The inventory hashes 38 output files totaling 4,392,602,461 bytes. Large raw and
extracted arrays remain local under narrow Git exclusions; restore them from
the inventory to reproduce raw-data checks in another checkout. The audit also
verified that both underlying public 8k reports were healthy, precision-passing,
divergence-free and parity-passing, while preserving their resource failures.
The pilot draws remain excluded from the future reference bank. Two independent
fits per backend cannot establish reference-bank accuracy.
