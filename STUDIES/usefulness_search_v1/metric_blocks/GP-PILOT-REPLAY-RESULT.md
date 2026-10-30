# Pilot and bounded-map replay

All four archived pilots were rerun serially. The preflight checks exact retained draws, total target calls and fitted map parameters; it is not new-map validation or an end-to-end speed comparison.

| Fold | Passed | Pilot gradients | Sampling seconds | Map fit seconds | JSON seconds |
|---|---|---|---|---|---|
| 0 | True | 659413 | 0.911918 | 0.008297 | 0.002901 |
| 1 | True | 631633 | 0.911469 | 0.009947 | 0.004987 |
| 2 | True | 659445 | 0.962548 | 0.011381 | 0.003956 |
| 3 | True | 681154 | 0.893790 | 0.007963 | 0.004198 |

Sampling time includes model construction and sampling after imports. Map fitting uses the prescribed400 positions but the complete pilot is charged. JSON timing includes only map serialization, not compiled target-data construction. Process supervision also includes imports, output and comparisons; its polling clock is not a precise short-duration timer. No clocks here establish superiority or replace prospective full-workflow timing.
