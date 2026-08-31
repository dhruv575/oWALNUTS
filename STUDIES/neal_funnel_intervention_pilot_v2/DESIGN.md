# Neal funnel intervention pilot v2 design

## Evidence and mechanism

Pilot v1 showed that refinement level 12 removed all refinement exhaustion and
corrected divergences, but 10,000-draw scale bulk ESS remained 27.8--143.4 and
maximum rank R-hat remained 1.0247--1.1094. Depth-stop rates were only
0.003%--0.53%, so increasing tree depth is not the smallest supported
intervention. Reverse-coarser stops were 11%--20% of retained transitions,
which indicates strong local refinement-level sensitivity but does not prove a
reversibility defect.

The separate 4x50,000 run used common zero starts, 2,000 warmup, target
acceptance 0.90, refinement 8, and reported scale R-hat 1.0029, bulk ESS 710,
and tail ESS 780. Its scale bulk ESS per 10,000 draws is approximately 142,
near the best v1 short cell, but it lacks corrected execution-time health
telemetry. This supports two possibilities: approximately linear ESS
accumulation needs a longer retained run, or dispersed initialization exposes
unstable finite-warmup adaptation.

The smallest general-purpose intervention is therefore robust initialization
of adaptation, not a looser numerical tolerance: enable the existing bounded
initial-step search and give windowed mass/dual-averaging adaptation four times
as many transitions. The 2x2 design separates that intervention from the
diagnostic initialization factor.

## Quantitative choices

- Target acceptance remains 0.90. V1's 0.95/refinement-12 scale bulk ESS was
  27.8, 143.4, and 101.6; it did not consistently dominate 0.90.
- Refinement remains 12 because it yielded 0 exhaustions in all six v1 cells.
- `max_error=0.5` and minimum microsteps 1 remain fixed. Altering either changes
  numerical work/accuracy rather than directly testing adaptation stability.
- Maximum depth remains 10 because v1's worst depth rate was 211/40,000 =
  0.5275%, below the 1% health limit.
- Robust warmup is 8,000, four times baseline and eight times the first 1,000
  transitions often used in exploratory runs. It provides multiple expanding
  metric windows after chains leave their initial region.
- Initial search is the existing bounded default: 4 momentum probes, at most
  16 bracket steps and 1,024 target calls. It chooses a coarsest-accepted macro
  step before dual averaging; it does not modify retained transition rules.
- Retention remains 10,000. A pilot scale ESS of 100 projects to 500 at 50,000
  under linear scaling, above the confirmation requirement of 400. Failure of
  that scaling is itself evaluated by the later confirmation.

## Interpretation

The robust policy advances only if it works under dispersed starts and becomes
insensitive to the controlled start factor. If common-zero cells succeed but
dispersed robust cells do not, the result is initialization dependence, not a
general-purpose sampler improvement. High reverse-coarser rates are reported
and correlated with ESS/work but are not optimized or thresholded post hoc.

No NumPyro sampling occurs in this mechanism pilot. If the robust policy
advances, confirmation freezes it and runs matched NumPyro on the same starts
and fresh confirmation seeds under the policy recorded in `protocol.json`.
