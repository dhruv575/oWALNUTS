# Fresh replication queue

Freeze the exploratory hybrid result before new seeds. Compare rebuilt WAL .9
and NUTS .999 on mixed10 and mixed100, hybrid coordinates, four chains,1000
warmup,8000 draws,depth11, unchanged reference and gates. Seeds956900021..28
for mixed10 and956900031..38 for mixed100. Eight seeds per case,32 fits total.
Serial execution on one pinned CPU, alternate engine order by seed, preserve
every failure. No tuning or further parameterization selection on these seeds.
Report sampling and worker costs separately. This confirms the chosen settings
on fixed synthetic data; it cannot establish out-of-dataset generalization.

Existing EC2, dedicated RAM staging at
/dev/shm/owalnuts-funnel-hybrid-replication-20261101, <=128MiB output and
<=2GiB/900s per fit. Preserve dependencies in the latest build lane. Archive
and hash-verify completed results locally before reclaiming any RAM staging.
The root disk has about1.08GB free, so do not start disk-staged expansions.
