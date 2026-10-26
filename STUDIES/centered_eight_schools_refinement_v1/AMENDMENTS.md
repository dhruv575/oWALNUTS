# WP82 amendments

## Amendment 1 (before any evidence cell)

The first launch (2026-10-26, from `7966207f`) ran no cell.

- **Cause.** `protocol.json`'s `source_commit_under_test` held a prose description instead of a git
  revision. The driver's source guard (`git diff --quiet <rev> HEAD -- src integrations Cargo.toml
  tests`) therefore failed, and phases T, E, C, R and F each exited at the guard. No cell file and
  no `tests.json` were written. An empty `summary.json` from `analyze` was discarded with the lane
  clone.
- **Change.** `source_commit_under_test` is now `70343cdf`, the library commit; prose goes in
  `source_commit_note`. Nothing else changes: seeds, arms, phases and rules are as frozen.
- **Effect.** This is committed before the relaunch, and the relaunch runs every phase from the
  start.
