# BridgeStan owned-worker lifetime diagnostic

Status: complete; the owned-worker arm met its preregistered acceptance
criteria on this host. The frozen preregistration is `PREREGISTRATION.md`;
`protocol.json` is its machine-readable matrix. This is a new append-only
study. The failed `bridgestan_lifetime_v1` study and its children were not
modified or rerun.

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

## Verdict

One frozen run produced all 720 planned records with no reruns:

| arm | children | process faults | correlated Event 1000 | faults including events |
|---|---:|---:|---:|---:|
| prior resident/scoped comparator | 180 | 17 | 18 | 19 |
| owned one-worker | 540 | 0 | 0 | 0 |

The comparator had 16 `STATUS_HEAP_CORRUPTION` exits, one 60-second timeout
that returned 1, and two nominal return-code-zero children with independently
correlated Event 1000; event-inclusive union was 19 faults. The owned arm had
zero nonzero exits, timeouts, missing outputs, incomplete heartbeats, and
correlated Event 1000. Its one-sided 95% zero-failure binomial upper bound is
`0.0055323` (0.553%).

All 167 paired cells with successful raw output in both arms had exact FNV-1a
sample fingerprints, target-call counts, recoverable-failure counts,
algorithm revisions, and observed sample counts. Thirteen comparator cells
had no raw output and therefore were not numerically comparable; no owned
output was missing.

Process-level median duration was 0.466 seconds for the comparator and 0.279
seconds for the paired owned arm (ratio 0.585). This does not mean channel
dispatch is faster: one-worker model loading was much shorter because it maps
one model instead of four, while median sampling time was about 3.1x
(diamonds), 3.7x (sblrc), and 5.1x (mesquite) the comparator. These short runs
are load dominated, so timing is descriptive only.

The owned-worker mitigation clears this diagnostic lifetime gate, but it does
not prove the historical root cause or general safety. The result is limited
to these three model binaries, four-chain/four-thread 4/4 runs, the recorded
Windows host, and one owned worker. Multi-worker Windows execution remains
unqualified. No merge, push, tag, or publication was performed.
