# AWS-specific map equivalence

For all four qualified saved AWS pilots, check affine and bounded targets.
Per arm use32 evenly spaced saved pilot positions (flattened8000) plus16 fresh
standard-normal transformed points, seed950800001+dataset. No fitting from
these check points. Keep the original tolerances: scaled coordinate error1e-9,
normalized log-density/Jacobian error1e-6,scaled chain-rule gradient error1e-5,
scaled24-functional error1e-6,all finite. Preserve all384 checks and failures.
Existing verified compiled model libraries; no recompilation or threshold change.
180s,one BLAS1 worker,2GiB/128MiB. This is implementation evidence, not efficiency.
