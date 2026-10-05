# SV prior and native adapter checks

The prior-sensitivity diagnostic took 0.204 seconds and uses illustrative priors; no fitting, market calibration or acceptance threshold. Its report and exact diagnostic/target/synthetic sources are preserved.

Nine native adapter correctness tests passed in 4.83 seconds: normalized values and reverse gradients against Target and independent JAX, scale/no-scale ablations, finite differences, T1 zero residual, immutable snapshots/ownership, reentrant calls and explicit rejection of extreme unrepresentable inputs. The actual isolated parallel-release runtime paths and hashes are recorded; its binary is not duplicated in this compact archive.

No sampler run, latency comparison, forecast quality or market-calibration claim is made by these checks.
