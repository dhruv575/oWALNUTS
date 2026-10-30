# Divergence replay reveals strong map stretching at failed proposals

All eight native quadratic validation fits were inspected without exclusions. The available selected endpoints alone did not establish a failure mechanism. Of81 retained divergences,76 occur in fold2/replicate1 (seed948400006), all in chain1 (zero-indexed). Their selected endpoints have rho3.2215--3.3178, median map-Jacobian condition505 versus120 for nondivergent endpoints in the same chain. Condition maxima across fits do not by themselves separate failures from passing fits. Every one of24 independent decoder-Jacobian checks passed.

The failing fit was replayed with native store_divergences=True. All40 common retained/warmup numerical arrays match exactly, including draws and NaN locations; all target-call counters match. Thus the76 captured start/end records belong to the original failed transitions. Fresh gradients at every recorded start match the stored gradients exactly, validating the coordinate interpretation. Both ends of all76 records evaluate finitely. The diagnostic made152 extra gradient probes, separately from sampling.

| Quantity | Median divergence start | Median divergence end | Maximum divergence end |
|---|---|---|---|
| Map Jacobian condition | 446.25 | 2690.52 | 239534.46 |
| Largest map singular value | 7.61 | 45.40 | 634.56 |
| Target gradient norm | 202.70 | 3568.95 | 199436.29 |
| Largest absolute transformed coordinate | 4.23 | 4.50 | 6.84 |

The divergent proposals encounter substantially larger map stretching and target gradients than their recorded starts, at moderate rather than astronomically large transformed coordinates. This supports examining transport-induced tail stiffness, but does not separate the map's contribution from the original GP curvature or prove a unique cause. These76 events come from one chain's excursion, not76 independent replications. No validation gate is changed, no draws removed, no performance/uniqueness claim made.

Next reviewed mechanism: investigate a bounded-feature triangular map that retains global invertibility while limiting derivative growth of quadratic terms, using unchanged pilot data and an explicit fixed saturation scale. First establish the derivative bounds and independently check inversion/Jacobians, then compare bulk geometry and the exposed proposal region without claiming fresh validation. Any chosen map needs new compiled-target equivalence checks, equal native controls and fresh full-chain validation. The current unbounded polynomial map and all failures remain preserved. A new map must not merely make the native comparator artificially difficult.
