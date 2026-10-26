### WP83-PYMC-GIL-FREE-DEFAULT-V1 — gil_free as from_pymc's default: not proposed (draws not reproducible on 3 of 10 models)

- Ordered time: 2026-10-26, `wt/gil-free-default` (base `aa7160bd`), prereg `a1bb05bd` before any cell. Lane 4 (cores 12-15), pinned, co-tenanted. Seeds 8383101–8383103, robustness 8383500.
- Design: 11 PyMC models (hierarchical x2, logistic, Poisson, AR(1), simplex/bounded, Data + dims + Deterministics, initvals, initvals + Data, Potential, StudentT); arms default C callable, mode=NUMBA callable, gil_free t1/t4; 4 x 1,000/1,000; robustness 50 x 3 four-thread gil_free runs.
- Outcome: gil_free never errored where the default ran; the initvals + Data model fails closed (NotImplementedError). Gates equal (30/30 cells); wall per gradient 0.13–0.46x the default; means agree (max |z| 4.4); robustness 0 faults, 0 non-identical. Not ≡ numba control on ar1 (1/3), simplex_bounded (1/3), data_dims_det (3/3; frozen vs shared graph); data_dims_det t1 ≢ t4 on one seed. 0/10 models identical to the C default (predicted).
- Predictions: held P3–P8; failed P1, P2.
- Decision: rule R2 fails, not proposed. Docs keep gil_free=True + threads=4 as the recommended opt-in. Follow-up: gil_free determinism across fresh vs warm numba/PyTensor caches; a default change would also need a callable wrapper (CFuncTarget is not callable).
