# Production settings screen (training only)

Reference fits deliberately use conservative settings and cannot establish
comparative speed. Screen native diagonal target_accept .9,.95,.99 (groups0..2)
against fixed WAL dense .9 (group3). Four chains,1100 warmup,4000 retained each;
native maxdepth10,jitter0. Seeds951500001..4. One fit per setting; this is settings
selection on exposed training data, not confirmation or a timing competition.

After independent reference audit, qualify all160 functionals: finite statistics,
Rhat<=1.01,bulk/tail ESS>=400,zero retained divergences,absolute mean error<=.1
referenceSD,SD relative error<=.1,mean error/combined MCSE<=4. Select native setting
with highest minimum bulk ESS per counted gradient among qualified candidates;
ties choose higher acceptance. Never choose a failed setting. WAL .9 is fixed.
Fresh-seed confirmation and precision-matched serial costs are required before
comparative claims. If no native candidate qualifies,preserve the failure and
review a separate follow-up; do not count it as WAL advantage.

Four concurrent workers,4cores each,BLAS1;each300s/3GiB/128MiB. Initial free disk
>=1GiB. No retries or extensions. Record full raw output and all call counts.
No heldout labels or predictive qualification. Independent raw audit required.
