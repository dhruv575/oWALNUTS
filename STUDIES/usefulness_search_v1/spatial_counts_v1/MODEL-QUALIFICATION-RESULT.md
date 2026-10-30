# Model validation status

Preparation retained3604 original coordinates,not the3605 claimed by package
documentation. Primary seeded20% inclusion contains712 points across200 cells.
Both elevation and gradient covariates are included. No heldout score was read
or computed for model selection. The frozen noncentered GP has205 parameters.

The compiled model failed its original double finite-difference check at step
1e-4. A diagnostic step sweep showed increasing discrepancies at smaller steps;
this was evidence to investigate numerical roundoff,not permission to choose a
passing finite-difference step. All8 original points were then checked against
an independent mpmath implementation at60 and80decimal digits under a separate
frozen protocol. All8 passed. Maximum scaled compiled-AD discrepancy2.53681e-5;
maximum60/80-digit derivative discrepancy6.79133e-9;maximum physical-f error
1.15399e-7;maximum proportional log-density error1.95275e-6. Inputs,high-precision
strings,supervision and failures are retained. A local audit rechecked every
numeric gate,source hash and point identity.

This numerically qualifies the unchanged target for the reviewed runtime smoke.
It does not erase the original finite-difference failure,establish posterior
accuracy,demonstrate predictive value,or improve the WALNUTS algorithm. The AWS
native/WAL smoke is running; reference and strong-control protocols come next.
