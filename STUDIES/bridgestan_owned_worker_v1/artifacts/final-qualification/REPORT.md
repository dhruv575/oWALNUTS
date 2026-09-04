# Final owned-worker qualification report

The final implementation at source commit
`81bf936ee9667856a8be5fcf117feaea2df3f830` completed the preregistered matrix
exactly once. No child was rerun.

## Results

| mode | planned | recorded | successful | faults | Event 1000 |
|---|---:|---:|---:|---:|---:|
| ordinary owned-one-worker | 540 | 540 | 540 | 0 | 0 |
| concurrent four-target-instance | 180 | 180 | 180 | 0 | 0 |
| combined | 720 | 720 | 720 | 0 | 0 |

All launch, process, raw, heartbeat, stdout, and stderr inventories contain
exactly 720 expected records. There were no nonzero exits, timeouts, missing
or incomplete outputs, incomplete heartbeats, or raw invariant failures.
Every ordinary child reported one effective replica. Every concurrent child
reported four target instances with one effective replica each and 16 calls
per instance (64 total).

Ordinary run A and run B were exactly equal for all recorded fields. The
concurrent observations from all four target instances were exactly equal.
Validation covered settings, fingerprints, diagnostic checksums, target-call
and recoverable-failure counters, algorithm revision, sample/probe counts,
dimension, names, model information, compiled/effective threading, execution
backend, and requested/effective replica counts.

The one-sided 95% zero-failure binomial upper bounds are
`0.005532292551836959` (0.553229%) for 0/540 ordinary children,
`0.01650522819566269` (1.650523%) for 0/180 concurrent children, and
`0.0041520953856636345` (0.415210%) for 0/720 combined.

## Event-capture reporting correction

The original `windows-events.json` is preserved unchanged. Its PowerShell
query returned exit code 1 with
`NoMatchingEventsFound,Microsoft.PowerShell.Commands.GetWinEventCommand`,
which means the exact execution window contained no Application Event 1000
or 1001 records. The original analyzer treated every nonzero query exit as an
unavailable event log and therefore emitted `accepted: false` despite
recording zero event correlations and zero event-parse anomalies.

The reporting-only `windows-events-supplement.json` repeats the query over the
same frozen UTC window while treating `NoMatchingEventsFound` as an available
zero-record result. It found zero events. With that classification correction,
the final diagnostic qualification gate is accepted. No code was changed
after execution.

## Scope and release status

This is a limited Windows GNU result on one host using three frozen WP35
model/data assets and short diagnostic runs. It supports the serialized
owned-one-worker policy, including process-wide serialization across
concurrent target instances. It does not qualify Windows MSVC, Linux, macOS,
the cross-platform package/wheel matrix, or multi-worker Windows execution.
Python `from_stan` remains disabled on Windows for 0.2. The final diagnostic
gate passes, but the overall release remains blocked pending those items.
