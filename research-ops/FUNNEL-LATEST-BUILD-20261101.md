# Latest-build research checkpoint

Completed and locally hash-verified:

- serial01:96 fresh installed-WAL/NUTS fits,589 files; mixed4000 passes6/8 WAL
  versus7/8 conservative NUTS. Earlier8/8 reliability did not perfectly replicate.
- latest01:108 fits,688 files. Rebuilt e7139bed and installed binaries have
  distinct hashes but all36 paired trajectories are bit-identical. Median
  old/new sampling-time ratio1.018, not a large improvement.
- latest-hybrid01:24 post-hoc control fits,158 files. Both engines4/4 on mixed10
  and mixed100. Sampling: mixed10 WAL .604s versus NUTS .845s; mixed100 WAL
  1.440s versus NUTS .803s. Original-case hybrid failed both engines0/4.

Full methods, failures, costs and limitations:
STUDIES/funnel_application_v1/LATEST-BUILD-RESULTS.md.
All132 new draw summaries independently recomputed; original96 serial summaries
also audited. No accuracy gates relaxed. No10x/general practical advantage.

Active bounded queue at this checkpoint:

- /dev/shm/owalnuts-funnel-hybrid-replication-20261101
- driver PID40190,32 serial fits, eight fresh seeds per concentrated case.
- Protocol: STUDIES/funnel_application_v1/HYBRID-REPLICATION.md.
- Collect PROGRESS.json/STATUS.json and driver.log. Archive and SHA256-verify
  results locally after completion; tmpfs alone is not durable evidence.
- Dependencies: /dev/shm/owalnuts-latest-e7139bed and the original root-disk
  /home/ubuntu/lanes/funnel-application-20261101/model.so and monitor module.
  Do not reclaim them while the queued fits are active.

Existing EC2 18.223.111.36 remains running. Root has about1.08GB free (only
~9MiB above the1GiB floor); new evidence/builds were staged in executable RAM.
Build and test dependencies were isolated, existing environments preserved.
No evidence deletion, new instances, trading or deployment. Raw draws, source
archive and both extensions are retained locally but excluded from Git.
Unrelated options-flow endpoint_exact_controls.py edit remains untouched.
