# Related-work recheck during frozen validation

Checked2026-10-30; no policy changes follow this reading.

[Bales et al., Selecting the Metric in Hamiltonian Monte Carlo (2019), section3.1](https://arxiv.org/html/1905.11916v3)
already proposes automatic metric selection using transformed local Hessian and
sample-covariance eigenvalues; its switching benchmark selects among metric
candidates during warmup. Therefore automatic switching, Hessian information and
fixed preconditioning are not our novel contribution.

[Seyboldt, Carlson and Carpenter, Preconditioning Hamiltonian Monte Carlo by
minimizing Fisher Divergence (2026), sections2.4 and3](https://arxiv.org/html/2603.18845v1)
provides diagonal, dense and low-rank Fisher estimators and an adaptation schedule.
Our algebraically qualified dense estimator is attributed to this work. The
current staged baseline does not replicate its whole initialization/update schedule.

[BlackJAX metric-estimator documentation](https://blackjax-devs.github.io/blackjax/autoapi/blackjax/adaptation/metric_estimators/index.html)
documents Fisher-score diagonal/low-rank estimators alongside covariance methods.
Any implementation comparison needs a pinned version and matched validation;
documentation availability is not performance evidence.

The specific leave-one-chain-out worst-direction score-prediction gate is a
candidate empirical safeguard. This limited search does not establish novelty,
statistical reliability or theoretical guarantees. Even a passing fresh screen
must be followed by stronger schedule/estimator comparisons, broader targets,
and an ablation separating the gate from the preconditioner. Do not inflate a
six-target result into general-purpose superiority or a submission-ready claim.
