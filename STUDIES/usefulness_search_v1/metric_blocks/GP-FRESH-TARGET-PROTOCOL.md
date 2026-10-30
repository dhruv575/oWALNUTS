# Fresh-map compiled-target equivalence

For all four qualified fresh pilots, test both affine and bounded targets using the existing verified compiled bounded GP library and newly constructed target data. Per arm use32 evenly spaced unconstrained draws from independent reference group0 (flattened32000 retained draws) plus16 standard-normal transformed points, seed949700001+scenario. Reuse the same physical/reference and random points for both arms as specified; this is implementation validation, not performance selection.

Require finite values throughout, decoded-coordinate scaled error<=1e-9, full normalized log-density plus constant-Jacobian error<=1e-6, scaled chain-rule gradient error<=1e-5, scaled original24-functional error<=1e-6. Preserve all384 point checks and every failure; no map/point exclusion or tolerance change. No fitting from reference draws. BLAS1,one bounded worker180s/2GiB/64MiB; no compilation required.
