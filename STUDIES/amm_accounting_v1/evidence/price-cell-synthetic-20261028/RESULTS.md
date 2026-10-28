# Single-cell synthetic posterior check

The fixed million-proposal forward reference accepted 74,311 joint draws with
zero nonfinite proposals. NUTS saved four chains of 4,000 retained draws after
2,000 warmup iterations per chain. All five coordinates passed the declared
Rhat and bulk/tail ESS thresholds; there were zero divergences. Maximum absolute
mean discrepancy was 1.734 combined standard errors, below the fixed flag of 4.
This supports posterior agreement for this T=1 fixture only, not long-window
fidelity, historical observation semantics or an algorithm advantage.

The original worker exited 1 after saving all draws and the trace: ArviZ returned
a one-element array where `float()` expected a scalar. The supervisor preserved
that failure, drained its process group, and recorded 15.919 seconds elapsed,
1.934 GB peak RSS and 5.975 MB output. Reporting was recovered separately from
the hash-bound saved evidence using `.item()`. No sampling was repeated and no
seed was changed. The original worker remains a recorded failed invocation.

Seed audit scope is the reachable AWS lane tree's seed-named JSON inventories,
excluding dependency/cache directories. It is not proof about unrecorded seeds
or opaque engine-internal derivations. Full draws remain on the AWS instance;
off-instance artifact preservation and an independent report reconstruction are
still required before closing this study.
