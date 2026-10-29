# Curvature scaling and local-error tuning: frozen 2026-10-29

Question: can WALNUTS's previously observed curved-target precision per draw
translate into a larger, repeatable native computational advantage? This is
an exploratory extension selected after geometry_precision_v1, not application
confirmation. No algorithm changes or deployment are part of this study.

Six exact targets: dimension 8 or 24, curvature b = 0.5, 2, or 5. Independent
standard normal latent pairs map to q_even=z_even and
q_odd=z_odd+b*(z_even^2-1). The determinant is one. Unlike the earlier single
banana pair, every pair is curved. All six cases must be reported. The known
inverse transform is supplied to the reparameterized NUTS control; any raw
geometry win must be contextualized against this exact control.

Calibration: two disjoint seeds per case/configuration, four sequential chains,
750 warmup and 3,000 retained draws. Six WALNUTS configurations: target accept
0.90/0.99 crossed with max_error 0.1/1/10. Six NUTS configurations: accept
0.90/0.99 crossed with default gradient-based diagonal, draw-based diagonal,
or low-rank mass. Same native compiled density, same latent initial states,
depth ten, one core. Both ABI adapters reject nonfinite proposals recoverably.
Both adapters are constructed for every fit, charging common setup to all.

Select one configuration per engine and case using calibration only: largest
number of fully qualified seeds; if both pass, lowest median kernel time;
otherwise smallest worst normalized gate violation, then median kernel time,
then lexical name. No validation-driven tuning or target selection. Persist
selection before starting held-out jobs. 144 calibration fits total.

Held-out: eight fresh seeds per case, independent retained budgets 3,000 and
6,000, same chain/warmup/depth settings. Four arms: selected WALNUTS, selected
NUTS, original WALNUTS .99/error1, and exact-reparameterized NUTS .99/diagonal.
384 fits total. When selected WALNUTS equals the default, its duplicate arm
uses the same seed and is not independent evidence. All jobs run, including
larger budgets after earlier success. Show fixed-budget results as well as
coarse first-success ladders; ladder costs include failed smaller budgets.
Missing/unqualified runs remain censored. Never substitute a favorable seed.

Accuracy: retain the earlier uniform-transform mean and tail criteria. Expand
the below-median joint and centered-product checks to every curved pair.
Mean tolerance .015, first-three-coordinate tail probability tolerance .01,
pair joint tolerance .02, centered-product tolerance .005. MCSE <= half the
tolerance; all raw coordinates and all functionals R-hat <=1.01, bulk/tail
ESS >=400; zero retained divergences and depth hits. Reparameterized samples
are mapped to the original coordinates before these identical diagnostics.

Evidence for a larger advantage requires at least 7/8 WALNUTS qualifying
ladders, no fewer than selected NUTS, and median matched native kernel-plus-
materialization cost ratio NUTS/WALNUTS >=1.5 on at least two of six targets.
Report total/import/setup/diagnostic costs and target calls separately, plus
paired exploratory bootstrap intervals (10,000 resamples). A lower interval
bound >1 is needed before describing a convincing within-target speed lead.
These are exploratory intervals, not multiplicity-adjusted confirmations.
Always display the exact reparameterization control. A draw-count lead or
repeated cold setup penalty alone is not a computational breakthrough.

Seeds: calibration715000000, held-out725000000, case stride1000000,
configuration stride10000, replicate stride100, budget offset0/1. Tests735000000
and offsets, bootstrap745000000. Target/ABI tests use separate seeds.

Existing EC2 instance, twelve exclusive cores, 180s/1GiB RSS/32MiB output per
fit, admission stops below 1GiB free or after one hour. Every process group
must drain. Preserve raw double-precision draws, errors, terminal receipts,
source hashes, and source identity after each phase. No retries under original
run names. Correct bugs explicitly and preserve any invalid runs.
