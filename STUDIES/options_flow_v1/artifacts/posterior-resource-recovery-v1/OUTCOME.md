# Saved public draws: analysis recovered

Both intended saved-draw analyses completed. Fit 0 required 77.5232802 seconds
of additional outer time; fit 3 required 77.2919399 seconds. The recovery
controller recorded 154.8216525 seconds in total. No sampling was repeated.

Both fits passed the full health and endpoint-precision gates at both 4,000 and
8,000 draws. All four predictive calculations reported quadrature convergence.
The independent terminal audit verified checkpoint gates, original input and
status immutability, contained execution and separately charged additional
costs. Its executable source, exact recovery code ZIP, provenance and output
hashes are retained under `independent-terminal-*`.

Together with the reference fits, this establishes that the pilot's four
independently initialized sampling outputs support the specified diagnostics
and predictive processing within the chosen resource limits. The original two
public resource procedures still failed on their adapter bug; this recovery
does not turn them into uninterrupted successful workflows. Do not compare
their original sampling-only costs against complete reference workflow costs.

Original public attempt plus recovery cost is about 223.79 seconds for fit 0
and 215.82 seconds for fit 3. These sums retain failure overhead and posthoc
processing, but are descriptive accounting rather than a clean paired speed
experiment. Original pilot plus recovery controller cost is 989.6721878 seconds.

Two fits per backend cannot establish reference-bank accuracy or bootstrap
coverage. The next step is to test compact-data admission and predictive-cache
analysis costs, then freeze a fresh independent bank. Pilot draws remain
excluded. Large extracted arrays remain local under narrow Git exclusions;
the terminal inventory binds their hashes for restoration and revalidation.
