# Exact planning result (draft, no qualification or sampling)

Executable: planning.py; immutable output planning-results.json; four tests passed in0.95s against existing scalar Clopper–Pearson and binomial-power functions. All arithmetic completed; no sampler ran.

The planning family deliberately uses37 simultaneous two-sided exact intervals:18 for usable-and-covering H/N,18 for possibly-covering(H+F)/N, and1 for usability. Requiring the lower H bound≥.85 and upper(H+F) bound≤.95 is a conservative failed-fit-robust coverage criterion. It does not select only successful fits. Conditional-on-success intervals may also be reported descriptively, but adding them as inferential claims would require another multiplicity allocation. This clarifies the earlier draft's alternative37-claim conditional/unconditional reporting family.

At conditional usable-fit coverage.90, dependence-robust lower bounds on probability that all18 coverage requirements plus usability lower bound≥.95 pass are:

| True usability | N800 | N1200 | N1600 | First integer N with ≥80% lower power | Public +10%reference estimated hours |
|---|---:|---:|---:|---:|---:|
|1.000|0|.520|.954|1328|27.77+3.30|
|.995|0|0|.744|1624|33.95+4.05|
|.990|0|0|.007|2026|42.36+5.04|
|.980|0|0|0|3430|71.71+8.52|

Zero means the union bound is uninformative, not that actual joint power is zero. Every integer up to the reported first crossing was evaluated; binomial discreteness means not every larger integer automatically has higher power. Validate the exact chosen N before freezing. At true usability.95, proving a lower bound≥.95 has only about the allocated type-I-tail probability, so80%power is unattainable at that boundary.

The marginal planning probabilities require iid generated datasets and specified joint usability/coverage rates; no independence between endpoints is assumed. H~Binomial(N,s*.90), H+F~Binomial(N,1-s+s*.90), success~Binomial(N,s). Apply union bounds first to the two coverage sides and then across18selectors plus reliability. No assumption is made about coverage of absent failed-fit intervals. Population worst-case bounds are[s*.90,1-s+s*.90], so failures consume the equivalence margin quickly.

These are serious multi-day CPU budgets, anchored only to the completed fixed-posterior costs. Prior-generated hard regimes can be slower or fail, and storage/reporting adds work. A ten-percent reference subset is a diagnostic resource choice, not independently powered reference calibration. Reference failures remain in their separate intended denominator.

Recommendation: first freeze a fresh T1000 resource/failure screen (draft32public datasets plus8preselected associative-reference checks), with full original gates. It cannot qualify calibration. At observed means this is about52minutes, but prior tails/timeouts may dominate. Keep it separate from a later confirmation. If usable probability appears below.99 or long-tailed costs dominate, diagnose computation before committing thousands of expensive fits; do not loosen coverage/failure gates. If confirmatory funding is available, choose an exact prospective count on the order of2026or more for the .99-usability planning scenario, with a reviewed bounded resource policy, and accept inconclusive/failed results. Never claim that a small feasibility cohort or the current fixed-posterior72successes establishes .99 usability across prior-generated datasets.
