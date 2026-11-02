# Fresh matched-budget confirmation and newer installed NUTS control

The primary runtime was owalnuts0.3.0/nutpie0.16.8, not a fresh build of the
current source. The conservative two-seed followup found both methods can
qualify; fixed4000-draw kernel ratios alone do not prove time-to-accuracy wins.

Use the existing main Python environment's nutpie0.16.11 and the same installed
owalnuts0.3.0 extension, loaded from its existing site-packages path. No package
installation or rebuilding sampler code. Add only constructor compatibility
for shared_var_keys. Verify native target/Jacobian/gradient preflight again.
The model library, data, references, flags and all pass rules are unchanged.

New-version NUTS calibration: noncentered .90/.99/.999,4000 retained,1000 warmup,
seeds956600001/2 by case. Choose fastest fully qualifying setting; if none,
use .999 as a conservative fallback and label calibration unqualified.
WALNUTS remains noncentered .90, fixed before these results.

Fresh eight-seed confirmation per case: weak956500011..18 and
mixed956500021..28. Each engine gets separate1000,2000,4000-draw fits with1000
warmup at the same seed/physical starts. All budgets run and are retained.
Ladder cost charges every failed smaller budget before the first qualification;
no qualifying budget is censored, not assigned a speed. Report successful pairs,
all failure rates, full-worker and kernel costs, target calls, and calibration
cost separately. No accuracy/precision gate or model changes. Do not pool cases
to hide a regression or interpret same-data seeds as new real-world datasets.

Run at most four worker processes with one CPU slot each, each worker pinned
to a distinct available CPU for an entire case/seed block, alternating engine
order by seed. Match cases/seeds across methods. Per job900s/2GiB; total lane
<=128MiB in a separate /dev/shm staging directory. Archive and hash-verify locally
before claiming durable preservation. No root-disk evidence deletion. Root
disk admission remains1GiB; staging is memory-backed, not a durable archive.

These jobs test an installed runtime, not the latest optimized source build.
Any promotion or broad performance claim needs that additional confirmation.
