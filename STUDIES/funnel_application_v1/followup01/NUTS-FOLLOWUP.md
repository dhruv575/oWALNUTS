# Stronger NUTS followup, separately labeled after primary results

Primary fresh validation: WALNUTS passed4/4; selected NUTS passed1/4. No NUTS
configuration fully qualified during calibration, so this is not enough to
claim a fair matched-accuracy speed advantage. All primary results remain.

Test NUTS under noncentered and hybrid coordinates, acceptance .99 and .999,
on both existing datasets. Each configuration gets two fresh seeds:
956400011/12 weak and956400021/22 mixed. Pair WALNUTS noncentered acceptance.9
on those same seeds. Same four chains,1000 warmup,4000 retained,depth11 and
unchanged reference/accuracy/precision gates. No post-hoc winner declaration:
report every configuration and require another confirmation for a chosen winner.
Run jobs serially, alternating WAL placement by seed; report timings and calls.

Root disk is now only about9MiB above its1GiB floor. Stage this followup in a
dedicated /dev/shm directory, at most64MiB, with900s/2GiB per job. It uses at
most one CPU for four sequential chains. Do not delete existing disk evidence.
Stream completed artifacts to the local workspace and verify every file hash
before calling them durably archived; tmpfs staging alone is not an archive.
Root disk remains above1GiB and the native runtime/source stays unchanged.

Additional numerical audit: compare quadrature with the analytically known
no-likelihood prior (mu variance4,tau half-normal,theta variance5,logit symmetry)
and recompute raw-draw functional summaries and frozen pass rules. This audit
does not change any reference or sampling setting.
