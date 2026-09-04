# BridgeStan owned-worker lifetime diagnostic

Status: harness committed before execution. The frozen preregistration is
`PREREGISTRATION.md`; `protocol.json` is its machine-readable matrix. This is
a new append-only study. The failed `bridgestan_lifetime_v1` study and its
children are not modified or rerun.

The comparator uses source commit `9edcbac` (resident DLLs plus scoped sampler
pools). The intervention uses source commit `29290a0` (one Windows-owned
BridgeStan worker). Both compile this study's same child source so fingerprints
and heartbeat boundaries are comparable.

The matrix contains 180 paired comparator children and 540 owned-worker
children. Each child requests four replicas and runs four chains on four
sampler threads for four warmup plus four retained transitions. On Windows the
owned binary reports one effective replica. Seeds `992001..=992180` and
`993001..=993360` are fresh diagnostics; WP35/WP36 evidence is forbidden.

## Pre-execution checks

```powershell
cd C:\dev\owalnuts-wt\bridgestan-lifetime\STUDIES\bridgestan_owned_worker_v1
python -m unittest -v test_run_stress.py
cargo +1.88.0-x86_64-pc-windows-gnu test --locked
python build_binaries.py
python run_stress.py verify `
  --comparator C:\dev\owalnuts-build-bridgestan-owned-comparator-9edcbac\STUDIES\bridgestan_owned_worker_v1\target\release\bridgestan-owned-worker-v1.exe `
  --owned .\target\release\bridgestan-owned-worker-v1.exe
```

`build_binaries.py` refuses to replace an existing comparator tree. It exports
the comparator commit, injects only this committed child manifest/source, then
builds both release children with their respective runtime code.

## Frozen run

```powershell
python run_stress.py run `
  --comparator C:\dev\owalnuts-build-bridgestan-owned-comparator-9edcbac\STUDIES\bridgestan_owned_worker_v1\target\release\bridgestan-owned-worker-v1.exe `
  --owned .\target\release\bridgestan-owned-worker-v1.exe
```

The parent creates an exclusive durable launch marker before every child.
Existing records are read, and an existing marker without a record is recorded
as an interruption; neither condition launches a child again. It captures
process codes, PIDs/start times, atomic heartbeats, raw output, stdout/stderr,
timeouts, Event 1000/1001, and path/PID/application-start-time correlations.
A correlated Event 1000 turns nominal process success into a study fault.

The owned arm passes only with zero faults of every registered class and zero
fingerprint mismatches among paired successful outputs. Performance is
descriptive. Zero faults in all 540 owned children gives a one-sided 95%
binomial upper bound of approximately 0.552%; scope remains limited to the
registered models, short run shape, BridgeStan build, and host.
