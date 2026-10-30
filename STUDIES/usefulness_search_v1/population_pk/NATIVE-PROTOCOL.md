# Native primary-mode comparison

Fresh seeds 938100001/2 for WALNUTS and 938200001/2 for nutpie NUTS. Identical
primary-Hessian whitening and four primary-mode perturbed starts; 1000 adaptive
warmup and 4000 retained draws, target acceptance .99, max depth 12. One core and
one thread per job; randomized order, four concurrent workers, 300 seconds,
2 GiB RSS and 64 MiB output per job. No rate-exchange moves. This is explicitly
a primary-mode efficiency comparison, checked against the independently qualified
exchange references; it does not bound omitted-mode mass.

Compare all 68 continuous functionals, retained divergences/depth, R-hat <=1.01,
ESS bulk>=400 and tail>=200. Report callback errors across the entire fit; do not
claim retained failures from unseparated warmup errors. Require max mean discrepancy
<=4.5 combined MCSE and <=0.1 reference SD for accuracy. Efficiency is minimum
bulk ESS per second; report paired seed results and median, not a broad superiority
claim from two seeds. A substantial application improvement remains unproven unless
strong alternatives and application-relevant uncertainty/score comparisons justify it.
