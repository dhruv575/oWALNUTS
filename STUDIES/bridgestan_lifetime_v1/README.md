# BridgeStan native-lifetime diagnostic v1

Status: implementation complete; diagnostic execution pending.

This is a Windows process-lifecycle diagnostic, not posterior evidence. The
engineering protocol was committed before implementation in
`PREREGISTRATION.md`; the exact 180-child-per-mode machine protocol is
`protocol.json`. WP35/WP36 evidence seeds and artifacts are out of scope and
must not be rerun or modified.

The child performs a short four-chain, four-thread sample through four
BridgeStan replicas, writes a deterministic retained-draw fingerprint, then
explicitly drops the target between durable heartbeats. The parent runs the
historical baseline before the fixed executable, creates immutable pre-launch
markers, never reruns an attempted child, records return-code forms and
heartbeats, and captures relevant Windows Application events.

The final verdict, exact counts, finite zero-failure bound, binary/model hashes,
and any parity limitation will be written here after the single execution.
