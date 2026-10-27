# WP97 recovery

Initial local inspection on 2026-10-27 found the study at `c899cf95`, with smoke
still pending in its preregistration and no local evidence cells. Remote inspection
then confirmed that only the smoke had run. Recovery completed all 22 evidence
cells without reruns; [README.md](README.md) records the actual freeze, completed
verdict and archive locations. The remote lane is
`/home/ubuntu/lanes/pool_confirm_v1`. The procedure below preserves the recovery
discipline; it is not an instruction to rerun this completed study.

1. Inspect remote processes, lane logs, Git HEAD/status, the `prefreeze` directory,
   and `repo/STUDIES/pool_confirm_v1/artifacts` before running anything. Archive
   existing smoke, source, logs, and evidence with hashes. The existing smoke
   driver deletes its output directory, so do not invoke it over an existing
   `prefreeze` tree.
2. Copy `audit_inventory.py` alongside the original remote `protocol.json` and run
   `python audit_inventory.py artifacts/cells --hash-draws`. It reads only and
   reports expected records, missing ticks, invalid JSON, duplicate/unexpected
   ticks, draw-size mismatches, and hashes. A complete record set can contain
   failed outcomes; it is not a statistical pass. An existing directory is never
   treated as completed work.
3. Reconcile remote smoke against the documented diagnostic seeds and source
   revision. If evidence has not started, record the smoke disclosure and freeze
   the unchanged protocol before starting evidence. If it has started, preserve
   the actual freeze/source history; do not backdate a freeze. Record any needed
   amendment before affected evidence is interpreted.
4. Coordinate exclusive use of cores 8-11 and 12-15 with the parent agent. The
   original `box/lane.sh 3` and `box/lane.sh 4` run the frozen cell order and skip
   existing output directories. Never remove an output to make it rerun. A host-
   interrupted cell needs a documented deviation and explicit recovery decision;
   an ordinary failure is a result. There are 22 cells and 202 reference ticks,
   not 606 reference ticks.
5. Launch each lane detached with separate stdout/stderr logs, a PID record, and
   an exit-code file written on exit. The driver also emits `LANE-FINISHED`.
   Check both the exit record and inventory afterward: a successful driver exit
   does not mean every statistical cell passed. Avoid long-lived polling shells.
6. Run the original `analyze.py` on the box, in the pinned study environment and
   on the study's assigned cores, writing a new output directory. Pool arithmetic
   wall time is part of the frozen 400 ms rule; laptop analysis cannot supply the
   official latency measurement. Preserve the first official output and machine
   context instead of selecting a more favorable timing rerun.
7. Run `audit_reference.py artifacts/cells --out <new-output>/reference-audit.json`
   in the same environment. This supplements the original `h_next` gate with
   rank-Rhat, bulk/tail ESS, and MCSE of `mu`, `log_sigma`, `beta`, and `h_last`,
   plus retained-chain divergences. It never changes the frozen qualification
   verdict. Report supplemental failures alongside any original pass.
8. Copy all raw draws, attempted references, logs, summaries, source identities,
   and manifests locally; verify hashes before any remote cleanup. Write the
   README and ledger entry, regenerate checksums, and ask the parent to integrate
   the completed branch. No library default changes follow automatically.

## Interpretation boundaries

The primary headline requires one exponential-weighted `(K, H)` configuration to
pass on both datasets, at least 285/300 ticks pooled, at least 90/100 per seed,
and the frozen drift bound. Missing or failed ticks remain in the denominator.
The current analyzer suppresses entirely missing cells from descriptive group
rates (although its seed-count check prevents a false headline pass); reconcile
all expected cells before publishing those rates or make a documented reporting
correction. A missing earlier warm draw can also break lag construction; preserve
the missing outcome rather than silently shortening the pool.

Weight ESS describes weight concentration, not independent MCMC information.
The four-chain estimate of pooled-quantile MCSE is a diagnostic. Fresh sampler
seeds on previously inspected data test Monte Carlo reproducibility, not market
generalization. Volatility quantiles remain quote proxies; this study alone does
not establish a complete pricing/inventory policy or profitability.

Audit-tool checks run only on temporary synthetic fixtures:

```text
python -m unittest discover -s STUDIES/pool_confirm_v1 -p test_audit_inventory.py -v
```
