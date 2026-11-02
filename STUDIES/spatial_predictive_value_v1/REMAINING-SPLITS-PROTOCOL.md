# Remaining preplanned same-site sensitivity checks

Complete both original reserved thinning seeds952000003/4, without selecting
which result to retain. The seed2 check has a smaller, inconclusive advantage
over cheap counts; preserve that result and the failed primary gate.

Use the exact reserved_worker.py procedure, changing only thinning seed to
952000000+split_index, native inference/initialization seed955100000+split_index,
GP predictive seed955200000+10*split_index and terrain predictive seed one above
that. All models, priors, training-selection grids, diagnostics, evaluation and
budgets remain unchanged. Do not treat the overlapping census splits as new
sites or independent replication, and do not pool their cells as independent.

Separate lanes for indices3 and4, at most eight CPU slots combined, 900s/2GiB/
32MiB per lane. Before either launch, free disk must exceed1GiB plus both full
32MiB reservations. Preserve failures and raw draws. No evidence cleanup or
new AWS resources. The next research priority after these checks is a genuinely
independent dataset or a decision task where uncertainty has measurable value;
do not tune this model to improve the now-exposed primary holdout.
