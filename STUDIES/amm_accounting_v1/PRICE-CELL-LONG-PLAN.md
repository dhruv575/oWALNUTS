# Fixed long-window synthetic readiness panel

Status: frozen design, launch requires seed audit and source-bound monitored
runner. This follows successful T1 rejection-reference agreement. It does not
replace that independent reference with a claim that MCMC diagnostics prove
fidelity. Historical market observation semantics remain separate.

Four fits: T in {12,250}, log-price cell width in {0.001,0.00001}, ordered
(12,.001),(12,.00001),(250,.001),(250,.00001). Use the deterministic fixture in
price_cell_fixtures.py: two sinusoidal components with repeated levels every
five observations, nearest fixed-width cells and initial log price zero. These
are stress fixtures, not random prior draws, SBC or empirical market data.

Each fit uses the same candidate Stan target, four chains and four cores,
2,000 warmup and 4,000 retained draws per chain. Fix target_accept=.9,
maxdepth=10, low_rank_modified_mass_matrix=False and transform_adapt=False.
Initial center is [2*log(.005),log(.2),0,zeros(T),zeros(T)]. Proposed sample
seeds are 398124000+2*j, model seeds the subsequent integer, for j=0..3.
Audit these against existing seed inventories before launch.

Run on disjoint four-core groups, four jobs concurrently. Bound each job to
600 seconds, 4 GiB process-tree RSS and 256 MiB output; outer limits 660 seconds,
18 GiB RSS and 1.25 GiB output. Preserve timeouts and every fixed slot, do not
extend or replace seeds after observing results. At least 3 GiB free disk is
required before admission. Save full warmup and posterior traces and source
hashes, with process-group drain and final output checks.

Report rank Rhat, bulk/tail ESS, means and mean MCSE for every parameter
coordinate, divergences, maximum-depth saturation and wall/resource costs.
Declared diagnostic thresholds: Rhat<=1.01, bulk/tail ESS>=400 and zero
divergences. Report failures without dropping coordinates or fits. Tail-depth
saturation is a separate warning, not silently included in a pass claim.

Purpose: expose long-path geometry and narrow-cell numerical failures before
building a larger reference comparison. Passing is readiness evidence only.
Posterior fidelity beyond T1 still needs independent methods/reference checks;
predictive performance, decisions and profitability remain untested here.
