# WP88 bounded reference diagnostic audit

Post-hoc diagnostic, 2026-10-27. No sampler execution, archived evidence modification or revision of the original qualification verdict.

## Selection and provenance

For each of ref-sim-N250 and ref-real-N250, sort stored successful tick records by tick and select indices 0, len//2, len-1. No outcome-based selection.

Both datasets select ticks 0, 50 and 100. The simulated reference has 101 successful stored ticks; the real reference has 51 successful stored ticks and 52 raw files (one additional attempt). All selected records keep the four original chains at attempt 0.

The compact draws are mu, log_sigma and h_last, stored as little-endian float32; all six selected files have the expected 960,000 bytes and finite values. Predictive innovations, quantile definitions and chain selection follow the original protocol. The recomputed predictive R-hat equals the recorded value exactly for all six selected ticks.

`results.json` includes SHA256 hashes of the protocol, original analysis, tick logs, six selected raw files and this audit script, plus package versions and all coordinate diagnostics. `audit.py` reproduces this report using the isolated WP96 analysis environment (ArviZ 0.23.4, NumPy 2.5.4).

## Results

| Reference | Tick | Max coordinate R-hat | Min coordinate bulk/tail ESS | Kept-chain divergences | P50 relative MCSE | P95 relative MCSE |
|---|---:|---:|---:|---:|---:|---:|
| ref-sim-N250 | 0 | 1.000109 | 45310 | 0 | 0.090% | 0.207% |
| ref-sim-N250 | 50 | 1.000049 | 44711 | 0 | 0.092% | 0.198% |
| ref-sim-N250 | 100 | 1.000125 | 40178 | 0 | 0.079% | 0.160% |
| ref-real-N250 | 0 | 1.000092 | 22364 | 0 | 0.115% | 0.309% |
| ref-real-N250 | 50 | 1.000196 | 22688 | 0 | 0.135% | 0.319% |
| ref-real-N250 | 100 | 1.000031 | 24586 | 0 | 0.129% | 0.260% |

No selected coordinate exceeds R-hat 1.01 or falls below bulk/tail ESS 400. All six selected references have zero retained divergences. The selected real-data references have higher predictive quantile MCSE than the selected simulated references, but all are well below the study's 2% P50 and 5% P95 tolerances.

## Interpretation

This bounded check finds no evidence that the predictive-only reference gate concealed poor mixing of the saved globals or endpoint latent at these six ticks. It does not establish diagnostics for all reference ticks, the full latent path or beta (not stored in compact draws), agreement with an independent inference algorithm, forecast calibration, executable quote accuracy or profitability. The original predictive-only gate remains a limited test; the audit neither strengthens its definition retrospectively nor changes WP88's verdict.
