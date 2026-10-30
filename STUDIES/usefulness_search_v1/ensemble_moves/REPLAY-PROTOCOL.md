# Exposed Lotka mechanics replay

Frozen before execution. This is not a fresh efficacy test or reference study.
Use final positions, fixed mass and step sizes from bounded-init run01/012,
seed 939100003, whose second walker occupies a separate basin. Compare local
WALNUTS alone and WALNUTS plus one sequential ensemble MH sweep after each ten
local transitions, for 100 chunks. Common local seeds 940200001+1000*chunk;
separate proposal RNG 940300001. Four walkers; max depth 10, max error 1.
Proposal factors diag(1/sqrt(momentum mass)), fixed throughout; t degrees 5.
No warmup, tuning or density-ranked rescue. Serialize both arms, with separate
600-second/2-GiB sampled RSS/64-MiB output bounds. Save every local draw and
post-sweep position, proposals accepted, invalid evaluations, actual target
calls, divergences and depth stops. Any domain exception becomes a rejected
nonfinite proposal and is counted; invalid current density is fatal.

Interpret only mechanics and descriptive trajectories. Do not infer mode mass
from log density or report walker-based independent-chain ESS. No NUTS speed
comparison: this uses a Python BridgeStan callback. A fresh independent-ensemble
screen with both augmented and unaugmented NUTS remains required.
