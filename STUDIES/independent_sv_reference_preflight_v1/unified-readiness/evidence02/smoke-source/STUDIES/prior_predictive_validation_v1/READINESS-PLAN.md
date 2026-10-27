# Literal full-worker readiness plan (unexecuted)

Purpose: validate the complete candidate, side-score and independent-reference worker paths before any of the 32 study streams are generated. This development check is not calibration evidence. Parent approval and frozen source manifest are required before remote execution.

## Isolated environment

Create one NEW Python 3.12 venv under a fresh readiness lane. Never modify the two existing environments. Install exactly requirements-unified.txt plus the existing native wheel `/home/ubuntu/lanes/resident-predictive-build-20261027/wheels/owalnuts-0.3.0-cp310-abi3-manylinux_2_34_x86_64.whl`, SHA256 `b64b1f2aed4bd58e585a9679a67e5840fba971ccf9985cdd85054544e60a1211`. Resolver failure is final for this attempt: preserve output and do not relax pins or retry. Save pip --report, complete installed distribution versions, pip freeze and pip check. Pin resulting transitive packages before study freeze. No arviz[all] extra, which conflicts with nutpie's zarr requirement.

Install envelope: 600 seconds, sampled 4 GiB RSS, 3 GiB fresh-lane disk, TERM/KILL drainage. This disk allowance includes the new environment and download cache; campaign output retains its separate 1 GiB cap. Exact symlink-preserving interpreter path, prefix/base-prefix, Python version, executable hash, all installed native module hashes and relevant source entry hashes are recorded. Loaded owalnuts native hash must equal `db2c445a7a94da67d55d22d3b367c44544630655f07c88068e5456a2c7d93863`.

Existing BridgeStan SDK `/home/ubuntu/.bridgestan/bridgestan-2.9.0` is read-only. Makefile SHA256 `21f9f85c5d2390ba61cfb23015514b4f7dcb678b9f89927ece6bc43ec4eafeee`; record SDK source tree inventory, stanc/compiler versions and captured actual compiled-library hash. Each sentinel continues to compile independently through the public API inside its own TMPDIR; no private cache or forked sampler state.

## Literal development workload

Use 283 deterministic literal returns (repeat `[.001,-.004,.003,.002,-.0005,.0007,-.0022,.0015]`) and a constant literal latent array at `mu=2*log(.005)`, with `log_sigma=log(.2), beta=0`. These are engineering fixtures, not prior-predictive draws. No generator call or reserved study RNG is permitted.

Development seed reservation is in DEVELOPMENT-SEEDS.json: initial993711000, warm993712000, independent sample993713000/model993713001. Raw chain ranges and standard splitmix outputs are compared with the study's reserved seed inventory, plus a bounded tracked-source search across active worktrees. Opaque independent-engine internal derivation is not claimed audited.

Under one external 600-second envelope, execute fresh subprocesses sequentially in the unified env: candidate full initialization plus32 K400 updates (180s); both side scores for32 origins (90s); one independently compiled N250 reference with4chains,2000warmup,4000retained plus full observed-return evaluator and ArviZ diagnostics (300s). All use cores0-3/BLAS threads1. Imports, JIT, compile, serialization and hashes are included. Preserve every failure without replacement/retry. The reference uses the development seed override explicitly; the production reserved base is never consumed. Verify candidate score arrays, candidate/reference delta-density/PIT MCSE availability, full reference float64 joint shape4x4000x4, all side statuses, source/native hashes before/after and owned-process drainage. Numerical diagnostic failures are recorded, not hidden or called convergence qualification.

This plan currently precedes the development-entry implementation and exact source/runtime manifest. It is not executable authorization. Measured fresh-worker startup/JIT/compile costs will inform final conservative phase caps before study outcomes; proposed study caps are internal2880s/external3000s, candidate1200s, sides600s, references900s, report120s,4GiB RSS. No market-value inference: NIG-only comparison is insufficient against stronger rolling Student-t/EWMA alternatives.
