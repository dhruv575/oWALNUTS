# Exact live-ensemble proposal: correctness passes, mixing screen fails

2026-10-30. Research-only prototype; no library or default changes. Continuing
usefulness goal remains active. This is not a demonstrated algorithm advantage.

The sequential Student-mixture MH implementation passed density parity
(maximum log error 1.07e-14), accepted-flux parity (7.11e-15), and one-sweep
stationarity checks on 12,000 independent ensembles per known target. All
stationarity |z| were <=1.19, including a broad lower-density mode holding 80%
of probability. Restart integration actually evaluates changed positions, and
subsequent draws match ordinary single-chain fixed-kernel calls exactly.
These establish limited implementation correctness, not mixing.

The initial validation had a wall timeout but no enforced RSS supervisor. Its
canonical repeat used identical seeds and source under sampled RSS supervision;
it is verification, not an independent statistical replication. Both checks
exited normally, groups drained, source hashes unchanged. The validation and
integration checks took 17.96s and 0.33s under the supervisor.

## Exposed Lotka replay

The first replay mistakenly assumed the final saved draw of the previously
failed chain was still in the discrepant basin. A complete density audit found
that it had escaped late in the original run. Preserve that run: no ensemble
proposal accepted and both arms' draws match exactly. This does not overturn
the original failed whole-run diagnostics.

The separately versioned correction starts at the first saved draw, verified
to be in the discrepant region. Both arms retain the original fixed step and
momentum mass; source convention is `p ~ N(0,M)`, so the proposal factor is
`diag(1/sqrt(M))`. In this exposed replay the augmented arm accepted 2/400
proposals. Its second walker was above proportional log density -35 at the
first ten-transition checkpoint; the plain arm first did so at checkpoint 19.
This threshold was chosen post hoc to describe trajectories, not to define a
true mode or infer probability. Total target calls were 117,014 versus 116,563;
both had zero callback errors, divergences and depth stops. A single exposed
rescue is not efficacy evidence. Python and Rust density constants differ;
their ratios agree in meaning, and the replay uses Python consistently.

## Fresh known-target screen

All 128 frozen jobs finished in 28.75s with unchanged inputs, no job failures,
callback errors, divergences or depth stops. Four walkers per ensemble; 16
independent ensembles for each dimension/start/arm. Uncertainty uses ensemble
estimates, never treats interacting walkers as independent chains. See
MIXING-PROTOCOL.md and mixing-analysis01/SUMMARY.json for every functional and
gate. The target's positive-region probability is 0.2000253.

| Dimension | Start | Plain estimated probability | Augmented probability (SE) | Plain RMSE | Augmented RMSE |
|---|---|---:|---:|---:|---:|
| 1 | all broad | 0 | 0 (0) | 0.2000 | 0.2000 |
| 1 | both regions covered | 0.2500 | 0.3422 (0.00595) | 0.0500 | 0.1440 |
| 8 | all broad | 0 | 0 (0) | 0.2000 | 0.2000 |
| 8 | both regions covered | 0.2500 | 0.3432 (0.02577) | 0.0500 | 0.1745 |

**Frozen verdict: FAIL in all four configurations.** Many accepted proposals
do not imply exploration. Cold ensembles never reached the missing region.
Every covered augmented ensemble retained between one and three positive
walkers at every saved checkpoint. A post-hoc calculation of the product-target
positive probability conditional on this occupancy constraint is 0.33697,
consistent with the observed estimates. This supports a finite-run occupancy
bottleneck: the last walker in a region has little reverse proposal density
when the complementary ensemble contains none there. The heavy-tailed proposal
still has full support; no claim of mathematical nonergodicity is made.

The local-only arm is also inaccurate. Fixed conservative tuning here is a
mechanism control, not a strong tuned NUTS benchmark. This negative screen
does not establish that WALNUTS is worse generally, nor does it justify an
application campaign with this proposal.

## Evidence and next question

Raw draws, protocols, initial failed replay assumption, audits, package versions,
model binary/data/source, installed sampler/BridgeStan modules and supervisor
are archived together. See archive/S3-VERIFICATION.json for exact-version
restore verification. No remote originals are reclaimed.

The next reviewed mechanism is a fixed proposal bank learned before retained
sampling, so a region remains proposed after its last live walker leaves.
It must pay for discovering that region; oracle-supplied centers only diagnose
mechanics. See NEXT-DESIGN.md. This screen remains failed whatever follows.

Resource caveat: replay supervision scanned its log directory, not the sibling
draw directory; those small draw artifacts were checked after completion.
The fresh mixing screen supervises the complete job output directory. RSS and
output caps are sampled limits, not hard quotas. Root remains about 1.2 GiB
free; builds/runs stayed in tmpfs, with no instance shutdown.
