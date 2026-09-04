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

The strengthened derived acceptance requires all 180 comparator records,
four effective replicas in every successful comparator raw output, zero
faults of every registered owned class, `effective_replicas == 1` in every
owned output, and zero mismatches in all five claimed parity fields
(fingerprint, target/recoverable counters, algorithm revision, and sample
count) among paired successful outputs.
Performance is descriptive. Zero faults in all 540 owned children gives a
one-sided 95% binomial upper bound of 0.553229% (0.553% in prose); scope remains
limited to the registered models, short run shape, BridgeStan build, and host.

## Final implementation qualification

`FINAL-QUALIFICATION.md` is the append-only protocol for a fresh fixed-only
matrix over the final process-global serialization implementation. It freezes
540 ordinary two-run parity children and 180 four-target concurrent children.
The 992xxx/993xxx children are immutable and are not inputs to this launch.

Before launch, the final child and analyzer are checked with:

```powershell
cargo +1.88.0-x86_64-pc-windows-gnu test --locked --bin final_qualification
cargo +1.88.0-x86_64-pc-windows-gnu build --locked --release --bin final_qualification
python -m unittest -v test_final_qualification.py
python run_final_qualification.py verify --binary .\target\release\final_qualification.exe
python run_final_qualification.py prepare --binary .\target\release\final_qualification.exe
```

The one permitted launch command is:

```powershell
python run_final_qualification.py run --binary .\target\release\final_qualification.exe
```

The runner refuses any existing final launch/process record and cannot resume.
It validates the frozen WP35 asset hashes, records the final source/binary
identity, verifies historical raw Git objects against `14b1791`, launches
exclusively, and captures/correlates Windows events. Status before execution:
preregistered, not yet run.

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
`0.005532292551836959` (`0.553229%`; 0.553% in prose). Among the 18
comparator Event 1000 records, 14 were `0xC0000374`/`ntdll.dll`, three were
`0xC0000005`/`libwinpthread-1.dll`, and one was
`0xC0000005`/unknown-module.

All 167 paired cells with successful raw output in both arms had exact FNV-1a
sample fingerprints, target-call counts, recoverable-failure counts,
algorithm revisions, and observed sample counts. Thirteen comparator cells
had no raw output and therefore were not numerically comparable; no owned
output was missing, and all 540 owned outputs reported one effective replica.

Process-level median duration was 0.465882 seconds for the paired comparator
and 0.272474 seconds for the paired owned arm (ratio 0.585). The full
540-child owned median was 0.278604 seconds. This does not mean channel
dispatch is faster: one-worker model loading was much shorter because it maps
one model instead of four, while median sampling time was about 3.1x
(diamonds), 3.7x (sblrc), and 5.1x (mesquite) the comparator. These short runs
are load dominated, so timing is descriptive only.

The owned-worker mitigation clears this diagnostic lifetime gate, but it does
not prove the historical root cause or general safety. The result is limited
to these three model binaries, four-chain/four-thread 4/4 runs, the recorded
Windows GNU host, and one owned worker. Multi-worker Windows execution and
MSVC, Linux, and macOS qualification remain open, so the entire release is not
declared unblocked. No merge, push, tag, or publication was performed.
