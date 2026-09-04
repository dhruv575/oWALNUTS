# Append-only erratum

Issued after artifact commit `14b1791`. The preregistration, protocol, launch
markers, child records, heartbeats, raw outputs, stdout/stderr, and captured
Windows events are unchanged. No diagnostic child was rerun. Corrected
summaries below come only from re-analysis of the immutable records.

## Corrections

- The 18 comparator-correlated Application Error Event 1000 records comprise
  14 `0xC0000374` faults in `ntdll.dll`, three `0xC0000005` faults in
  `libwinpthread-1.dll`, and one `0xC0000005` fault whose module is unknown.
  The comparator event-inclusive union remains 19/180 and the owned arm
  remains 0/540.
- The paired-owned process-duration median is `0.27247365` seconds
  (`0.272474` rounded). The full 540-child owned median is `0.27860370`
  seconds (`0.278604` rounded). The reported ratio `0.58485525` (0.585
  rounded) compares paired owned with the paired comparator median
  `0.46588220`; it does not use the full-owned median.
- The exact one-sided 95% binomial upper bound after zero failures in 540 is
  `0.005532292551836959`, or `0.5532292551836959%`. Prose rounds this to
  `0.553%`.

## Strengthened derived acceptance

The regenerated analysis additionally requires every one of the 540 owned
raw outputs to report `effective_replicas == 1`. For each paired cell with
successful raw output in both arms, it compares all five claimed parity
fields: sample fingerprint, target-call counter, recoverable-error counter,
algorithm revision, and observed sample count. It additionally compares the
checksum, finite flag, dimension, requested replicas, thread/chain counts,
warmup/retained counts, compiled threading capability, child schema/status,
shape/seed, model/data identity, and diagnostic-only marker. The intentionally
different effective replica counts are checked against each arm's policy
rather than compared for equality.

These strengthened checks do not change the verdict: all 540 owned children
reported one effective replica, and all 167 comparable pairs match every
listed invariant. The result remains limited to the registered short-run
matrix and does not unblock the entire 0.2 release.

## Comparator completeness clarification

The final-review analyzer additionally requires exactly all 180 registered
comparator process records before the historical owned-arm acceptance can be
true. Every comparator child with a successful raw result must report four
effective replicas; every owned child must continue to report one. A
comparator child that faulted before publishing raw output cannot supply an
observed effective count, so it remains an explicitly unobservable fault
rather than being assigned a synthetic value. This is analysis-only: no
992xxx/993xxx child or immutable execution artifact is rerun or rewritten.
