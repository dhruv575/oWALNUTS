# Related work and remaining comparator gap

Primary sources checked2026-10-30. This is a focused check, not an exhaustive
novelty search. The local frozen validation continues unchanged.

Seyboldt, Carlson and Carpenter (2026) derive Fisher-divergence preconditioners
in diagonal, dense and low-rank forms. Their adaptation reuses scores generated
during warmup and updates metrics through multiple phases. Our dense fixed
Fisher arm uses their estimator in our staged protocol; it does not reproduce
their initialization, repeated adaptation or full sampler. Numerical stress
failures of our implementations are not failures of their published algorithm.
[Primary paper](https://arxiv.org/html/2603.18845v1).

Bales, Pourzanjani, Vehtari and Petzold (2019) already propose automatic metric
selection and a Hessian-based adaptation requiring fewer warmup observations.
Generic automatic selection, curvature use, and replacing a poor covariance
estimate cannot be claimed as new. Our saved-pilot criterion audit also is not
a full implementation of their sampler or schedule.
[Primary paper](https://arxiv.org/html/1905.11916v3).

Hirt, Titsias and Dellaportas (2021) adapt mass matrices using an approximation
to proposal entropy together with acceptance behavior. This is another existing
performance-driven adaptation objective, beyond empirical covariance alone.
[NeurIPS paper](https://papers.nips.cc/paper_files/paper/2021/hash/ef82567365bc6a0efb05d21837257424-Abstract.html).

Hird and Livingstone (2025) study linear preconditioning, including covariance,
Hessian and QR approaches. Their work is relevant to the assumptions and limits
of linear geometry changes. A numerical QR representation change here should
not be presented as a new statistical estimator.
[JMLR publication](https://www.jmlr.org/papers/v26/23-1633.html).

Our inference: the possible contribution is narrower than a new preconditioner.
It would have to be an empirically useful held-out score diagnostic and scale
repair, with explicit failure modes and a stronger end-to-end comparison. The
current six-target continuation gate is insufficient to establish that claim.
The Gaussian score identity and affine-invariance derivation explain the
diagnostic, but do not show it controls sampling error on nonlinear targets.

The maintained nutpie documentation exposes draw-covariance diagonal, Fisher
diagonal and low-rank options. This makes a native full-schedule comparator a
concrete next requirement rather than an unavailable idealized baseline.
[Official options](https://pymc-devs.github.io/nutpie/sampling-options.html),
[official Stan interface](https://pymc-devs.github.io/nutpie/stan-usage.html).

The PyPI0.16.11 CPython3.14 Linux wheel was downloaded locally and its SHA256
checked against release metadata. DOWNLOAD.json records the artifact, digest
and dependencies. It is not yet installed or sampled; the active validation
environment is unchanged. Inspect the pinned implementation before choosing
options: documentation and package versions can differ. Qualify the existing
BridgeStan library/data bridge and reference accuracy before model comparisons.
[Pinned release](https://pypi.org/project/nutpie/0.16.11/).

Next order: finish/audit the frozen validation; run the prepared numerical
preflight without overlapping timed workers; qualify native nutpie in a separate
environment. Preserve all older negative results and explicitly distinguish
fixed-estimator comparisons from full published-sampler comparisons. No result
yet establishes application value, uniqueness, profitability or paper readiness.
