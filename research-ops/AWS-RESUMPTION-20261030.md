# AWS research resumption, 2026-10-30

User increased the monthly gross budget and authorized renewed AWS use.
The existing owalnuts profile successfully reauthenticated. AWS Budgets returned
USD 120 limit and USD 63.09 actual spend (billing data can lag). The existing
instance i-05c712c79c74ae7f8 was stopped, then explicitly started and verified
running and SSH reachable at 18.223.111.36.

Initial live host inspection: 16-vCPU c7a.4xlarge, approximately 30 GiB available
memory, root disk 99% used with 1.1 GiB available. No research process appeared
in the top CPU process snapshot. Do not launch storage-heavy work until a
verified archive/cleanup pass establishes headroom. A bounded read-only disk
inventory is in progress; no evidence has been deleted in this resumption.

The independently running local fresh-data comparison remains active, with
38/48 fits observed complete and passing at this checkpoint. This partial
observation is not a terminal result or evidence of comparative superiority.
Next: finish and independently audit all 48 fits, archive exact executed
sources, repair the documented historical source filename collision, and
establish the fresh-data conditional-importance baseline.

Fresh-data comparison completed all 48 fits with qualified accuracy. The frozen
advancement rule failed: full-pilot-inclusive bounded WAL / raw WAL gradient
efficiency ratio 0.472325, dataset bootstrap 95% interval [0.415264,0.515577].
Sampling-only ratio 1.647290 [1.207396,2.309225] omits necessary setup and cannot
rescue this result. Matched bounded native comparison remains positive at
1.823174 [1.530845,2.171326], but superiority to that control does not establish
practical benefit. Four selected synthetic datasets limit generalization.
Independent audit and exact-source archive are now running.

2026-10-30: fresh-data importance baseline completed 6/8 qualified. Its sparse
scenario failed Pareto k twice; AWS post-hoc raw-weight audit found about 10%
weight below the grid's alpha=.1 lower bound. A separately frozen wider-grid
repair is launched at /home/ubuntu/lanes/gp-widegrid-repair-20261030 with eight
fresh seeds, fixed alpha lower bound .0001, unchanged accuracy requirements,
and 300-second per-job supervision. Initial import failed before any jobs or
results directory because psutil was missing. Installed psutil==7.2.2 (matching
local monitor environment), then launched the unchanged source bundle. Preserve
this administrative startup failure separately from inferential outcomes.
Bundle SHA256 eae617ad50df4b739640c203add529fd1017346bbd5c8283aa0b573577a8336a.
New-data comparison S3 exact-version restoration now verified in
research-ops/archive/gp-newdata-s3-20261030/VERIFICATION.json. No EC2 input cleanup
based on this archive; dependency archives remain separate.

The first job batch exited before inference: all eight workers could not load
libtbb.so.2. Preserve /home/ubuntu/lanes/gp-widegrid-repair-20261030/results.
A second distinct directory gp-widegrid-repair-20261030-v2 uses the unchanged
frozen bundle and the exact local libtbb.so.2 copied with SHA-256
4981698e2dbbae5b2f923ca6a4e5778ee0b8a58c0d4633074fd92049f3775c10.
LD_LIBRARY_PATH points only to this second directory's models folder. The new
batch launched with the original unused seeds after the administrative failure;
no posterior draws were produced in the first attempt. Verify its handle before
any restart. Supplemental runtime library must be included in final archive.

AWS map-equivalence audit passed384 points with near-roundoff errors. Operational
note: that audit used the180-second timeout and BLAS1, but its stated RSS/output
caps were not enforced by resource_monitor. No memory-bound compliance claim is
made for this audit; scientific checks and saved errors remain valid evidence.
The new full-cost run uses the scoped resource_monitor caps as specified.
New root /home/ubuntu/lanes/gp-qualified-cost-20261030; fresh production seeds
950900001..4; all28 workflows, AWS-qualified maps, unchanged replay tolerance.
Bundle SHA256 5aadc0df3e6cf0b1ef38cae8ac0fa64153a1fb2279ab14e0f8e2c20fa1b1f3bd.
Original failed timing batch stays at gp-full-cost-20261030. Disk was1.6GiB free
at launch; monitor the1GiB floor. No evidence cleanup occurred in this step.
