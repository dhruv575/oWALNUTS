# Metric-adaptation prior-art and baseline audit

Checked primary sources 2026-10-30 while fullshape02 runs; this does not change
that frozen experiment. No claim of an exhaustive novelty search.

* Bales, Pourzanjani, Vehtari and Petzold (2019),
  [Selecting the Metric in Hamiltonian Monte Carlo](https://arxiv.org/html/1905.11916v3),
  proposes automatic Euclidean metric selection and low-rank Hessian adaptation.
  Its comparisons include diagonal, dense and switching choices; the displayed
  benchmark timings exclude warmup. Automatic Hessian-based selection itself
  cannot be our novel contribution. A direct method comparison is outstanding.
* Hird and Livingstone (2025),
  [Quantifying the Effectiveness of Linear Preconditioning in Markov Chain Monte Carlo](https://www.jmlr.org/papers/v26/23-1633.html),
  analyzes covariance, diagonal, mode-Hessian and QR preconditioners, including
  cases where diagonal preconditioning worsens conditioning. Our diagnostic
  condition numbers alone do not establish mixing improvement or new theory.
* Seyboldt, Carlson and Carpenter (2026 preprint),
  [Preconditioning Hamiltonian Monte Carlo by minimizing Fisher Divergence](https://arxiv.org/html/2603.18845v1),
  develops diagonal, dense and low-rank estimators using warmup positions and
  scores. Its dense condition is S Cov(g) S=Cov(x), S=M^-1; regularization adds
  gamma I to both covariances. This is a relevant strong baseline for our small
  dense blocks, not a new estimator to claim as ours. Reported paper performance
  has not been independently replicated here.

Repository distinction: WP71 already tested the diagonal gradient-informed
sqrt(var(x)/var(g)) estimator inside existing Stan windows. Its 17-model screen
FAILED (geomean .983, passes43 to40, three new divergences). See
STUDIES/gradient_metric_v1/LEDGER-ENTRY.md. That result neither tests dense Fisher
adaptation nor validates the paper's complete initialization/update schedule.
Do not rerun the same failed diagonal variant as a supposedly new discovery.

Next-baseline requirement, conditional on a surviving candidate: derive and
numerically verify the dense matrix solution on Gaussian targets, then give it
the same pilot/remaining warmup as the candidate with every extra gradient call
charged. A standalone estimator test is not a reproduction of a whole published
sampler. Compare whole algorithms separately before claims against that work.
Current fullshape02 results remain governed by their original preregistration.
