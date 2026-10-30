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
