# Reviewed next mechanism: fixed proposal bank

Evidence to explain: live complementary proposals preserve the product target
but the 128-job known-target screen remains trapped in region-occupancy classes.
All cold ensembles miss the narrow region; covered ensembles overestimate it.
Do not retune this exposed screen until its gate passes or call its Lotka rescue
a general improvement.

Replace live walker centers with a frozen mixture bank collected before the
retained phase. For a fixed normalized proposal g, independent MH acceptance is
min(1, pi(y)*g(x)/(pi(x)*g(y))). Every component remains available even when no
current walker occupies its region. Use full mixture densities, positive fixed
weights and nonsingular Student factors. No retained-state bank updates in the
first prototype. Conditional on its fixed bank, each production chain preserves
pi; insufficient bank coverage still makes mixing arbitrarily slow.

Ordered gates:
1. Prove/check proposal density, accepted flux and exact-start stationarity.
2. A clearly labeled oracle-bank diagnostic can test whether retaining a region
   resolves the observed occupancy bottleneck. This is not discovery evidence.
3. Before claiming usefulness, learn the bank from a bounded, separately costed
   pilot with no supplied true centers/weights. Freeze the discovery procedure
   and fresh seeds before evaluating it. Broad starts must be included, and
   failed discoveries retained. A tempered exploratory pilot is a candidate;
   do not assume it succeeds or omit its cost.
4. Give fixed-bank moves to both WALNUTS and strongly tuned NUTS. Include the
   frozen mixture itself as an importance/Laplace approximation baseline: if
   cheap approximation already solves the problem, do not credit the sampler.
5. Independent chains conditional on a shared random bank do not establish
   unconditional uncertainty across discoveries. Replicate whole pilot-plus-
   production experiments and report both failure probability and cost/accuracy.

This is established independence-MH machinery, not a novelty claim. No default,
deployment, trading or application-success claim follows from a synthetic pass.
