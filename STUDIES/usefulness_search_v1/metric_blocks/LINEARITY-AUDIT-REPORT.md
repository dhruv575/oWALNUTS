# Leave-one-chain-out score-linearity hypothesis audit

Post-hoc audit of the same24 broad01/fishercompare01 pilot cells. Fit a full affine
score predictor on three chains, evaluate the held-out chain, repeat four ways.
Report worst directional R2 =1-||E R^-1||_2^2 where centered held-out scores=Q R.
This includes prediction bias and tests all linear combinations of scores, unlike
coordinate-wise R2. No sampler run, target evaluation, independent validation or
accuracy-selection guarantee is provided. Inputs and script hashes are recorded.

Worst directional R2 across held-out chains ranges .920--.941 for ARMA,
.942--.961 for arK, -.939-- -.544 for GP and -9.38-- -2.60 for eight schools.
GARCH ranges .088--.174. Proper-prior regression ranges -2.95--.909, including
one strongly negative case despite all four Fisher samplers passing. Positive
predictive value would separate the observed GP/eight-schools failures but miss
one good regression fit; this observation is explicitly hypothesis development.

Next candidate to freeze and test freshly: prefer Fisher only if all held-out
directions predict better than a constant score (worst directional R2>0), otherwise
use the existing stable-full-shape block policy with automatic fallback. Charge
scores, curvature probes, fitting and gate time. This combines prior mechanisms;
no novelty claim. Compare against unconditional Fisher, existing v4, automatic
and dense adaptation across fresh seeds, retaining reference and uncertainty gates.
Use target names nowhere in policy. Preserve the failed regression pilot in
design history. Need storage headroom audit before larger batch.
