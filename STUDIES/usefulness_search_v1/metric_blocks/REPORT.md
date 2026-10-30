# Metric audit: reject the R-squared block hypothesis; identify stable curvature

2026-10-30. No sampler policy/default changes. This is exposed-data mechanism
evidence, not efficacy or a demonstrated algorithm improvement.

Both passive instrumentation versions reproduce all 12 historical auto2 cells
exactly: every JSON field except wall time agrees, including all draws, starting
states, metrics, decisions, diagnostics and target work. Each bounded build
finished in about 19.24s; the first replay batch took 20.13s. All process groups
drained and frozen inputs remained unchanged. Source copies are isolated from
the production tree and historical evidence.

## The initial hypothesis is contradicted

In kidiq seed 927100003, coefficient-force R-squared values are .101, .261 and
.0647; the noise-scale coordinate is .783. In earnings seeds 927100001/2 the
coefficient values are likewise low, while the noise coordinate exceeds .5.
Thus one poorly fitted noise coordinate did NOT veto an otherwise well-fitted
coefficient block. A policy that merely retains coordinates with R-squared >=.5
would miss the desired blocks. The GP controls also have only one coordinate
above .5. Two GARCH cells have a positive three-coordinate subblock, but its
diagonally normalized condition number is only about 3.02--3.16. This provides
no strong motivation to implement the original R-squared-based block proposal.

## Direct curvature gives a different explanation to test

A second passive replay records four current-window states per chain, 16 per
cell. Offline negative gradient Jacobians are evaluated at two finite-difference
steps. All saved gradients match the target exactly; maximum relative step
sensitivity is 2.63e-6 across the audit. The separately supervised offline audit
uses 5,184 gradient calls and about .178s inside its worker. These extra calls
are not part of replay parity or claimed performance savings.

The named regression coefficient blocks are positive definite at every saved
state. Their trace-normalized precision shapes vary by less than 1.7e-13;
diagonally normalized precision entries vary by less than 7.1e-12. In earnings,
precision scale changes by factors 1.16, 126 and 3,168 across the three cells,
while the normalized condition number stays near 12,363. In kidiq the current-
window scale factors are 1.18--1.24 and condition number about 264. Multiplying
precision trace by sigma squared is constant to roughly 1.3e-12 relative range.
This agrees with the conditional Gaussian regression curvature X'X/sigma^2.

The force-regression gate pools an earlier window too; those earlier states
were not captured in this audit. Consequently the exact source of kidiq's low
pooled R-squared is not fully localized by the relatively settled current-window
snapshots. Do not infer a large unobserved scale excursion from this result.

In contrast, the GP latent block's trace-normalized shape varies by .516--.647,
with normalized-entry ranges .682--.727. Several full Hessians in GP, GARCH and
one earnings case are indefinite. Blindly using a full Hessian as a mass matrix
is therefore not justified. A stable positive coefficient block is a narrower
observation than global Gaussianity.

## Next bounded question

Current blocks were identified by model parameter names. That is not an automatic
algorithm. Before a sampling experiment, test a generic, name-free curvature
shape rule against the saved snapshots and known analytic models, charging every
probe. The rule must not mistake variable GP curvature for a stable correlated
block or install an indefinite matrix. See CURVATURE-DESIGN.md. Exposed states
may develop/debug a hypothesis; efficacy requires a frozen fresh broader screen
against existing automatic, full-dense and diagonal controls.

The earlier later-window and conditional-reconsideration screens remain failed.
This audit does not rehabilitate them. Keep the usefulness goal active.

The initial temporary workspace disappeared before archiving, without an instance
reboot or a cleanup command from this task. Its cause remains unknown. The first
analysis had been saved locally; the initial raw replay/curvature files were lost.
Both audits were then reproduced from the verified 218-member historical archive
in a dedicated mount outside /dev/shm, with durable copies after each completed
job. All 24 replays again match the baseline; the first analysis reproduces its
locally saved predecessor exactly. Curvature was recomputed from those verified
states. Recovery is not additional independent scientific replication.

Evidence includes both recovered source copies/binaries, all 24 reproduced
replays, historical inputs, target/model files, exact parity checks, raw curvature
matrices and monitors. See RECOVERY.md, RECOVERY-VERIFICATION.json and
archive/S3-VERIFICATION.json. Recovered evidence remains remotely. Build output
caps cover logs, not Cargo artifacts; builds stayed in the dedicated tmpfs.
Job RSS/output caps are sampled, not hard quotas. The loss is preserved in the
record rather than silently treating recreated raw files as the lost originals.
