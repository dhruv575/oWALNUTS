# Fresh conditional-importance accuracy confirmation

Use the unchanged conditional_v3 proposal algorithm and verified local grid from gp_conditional_local01. Four fresh seeds949200001..949200004,16384 proposals each. No proposal fitting to the posterior reference. Retain all four replicates and failures, no reruns/extensions. Preserve existing historical approximation results.

Evaluate the same24 quantities as the fresh sampler confirmation against ../gp_count/REFERENCE.json. Require finite weighted estimates, importance ESS>=400, Pareto k<.7, maximum mean error<=.1 reference SD, relative SD error<=.1 and combined-reference-MCSE mean z<=4. This prospectively tightens the historical SD threshold from .2 to .1 without changing proposal sampling or exact importance correction. Importance ESS and MCMC ESS are different diagnostics; do not rank methods by their numeric ESS alone. No competitive runtime or application claim from this accuracy replication.

Launch sequential workers after concurrent sampler confirmation finishes. BLAS1;180s/2GiB/64MiB per replicate,2GiB minimum free disk. Preserve exact draws, weights, proposal/target densities, all conditional solve/objective/factor counts and exact-target counters. Record cold subprocess supervision and worker times separately; full serial end-to-end comparison still requires repeated setup and matching precision, so do not equate these clocks with a fair sampler ranking. Include the preflight/grid preparation costs in any subsequent accounting.

Verify source, grid, reference and compiled target dependency hashes before/after production; archive and read back raw evidence. Accuracy confirmation of the approximation does not demonstrate WALNUTS advantage, uniqueness, profitability or goal completion.
