# Market replication operations

This packet contains the frozen seed reservations, batch supervision code and independent operational audits for the April, May and June 2026 replication. Scientific results are maintained in `STUDIES/market_replication_v1`.

- [Operational plan](PLAN.md) and [seed reservations](SEED-RESERVATIONS.json).
- [Readiness audit](execution-20261027/READINESS-AUDIT.json): all four engineering stages completed and drained; authorization changes were status-only.
- [Terminal audit report](execution-20261027/TERMINAL-README.md) and [machine-readable checks](execution-20261027/TERMINAL-AUDIT.json): all 33 jobs, 4,368 origins, 13,104 forecasts and 24 references accounted for, with frozen seed/source identities and resource limits verified.
- [Top-level tracked-file checksums](TRACKED-CHECKSUMS.sha256). The earlier [readiness checksum manifest](execution-20261027/CHECKSUMS.sha256) and [terminal checksum manifest](execution-20261027/TERMINAL-CHECKSUMS.sha256) remain unchanged.

These audits did not rerun sampling, scoring or statistical analysis. Full raw archives remain in main's `target` directory; this Git packet preserves source, bounded metadata and provenance rather than duplicating the raw archives.
