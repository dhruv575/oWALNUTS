# Curved target observer qualification

2026-10-30. All six direct/latent by WAL/diagonal-native/low-rank-native configurations passed pristine/disabled/enabled draw-hash and work parity, plus independent compact/full summary replay. The same analytic target code is used in all four binaries. Original-coordinate summaries in the latent representation include the nonlinear banana map before squaring or thresholding. Both independent quadrature forms agree within 5e-15: odd-coordinate P(x<0)=0.677659868383826 and P(x<-2)=0.5497900103494923. A separate 200,000-draw exact transformed-normal control passed frozen moment/probability tolerances.

All three latent controls passed frozen original-coordinate moment/probability checks and raw latent Rhat/ESS/divergence gates. Maximum Rhat was 1.00112; minimum bulk ESS across methods was 33,934 and minimum tail ESS 9,793. ESS above draw count is possible for anticorrelated chains; it is not a count of independent draws. No latent retained divergences occurred.

Direct-coordinate runs are NOT all qualified: fixed-step WAL had maximum Rhat 1.01647 and minimum bulk/tail ESS about 201 despite zero divergences; diagonal native had three divergences; low-rank native had none and raw diagnostics within thresholds. The protocol did not declare direct posterior accuracy from these diagnostics. Do not interpret zero WAL divergences as better inference, or use these preflight runs to claim efficiency. These are four-chain checks, not replicated-MSE validation.

All builds and tests passed (WAL original/observed 8 each, native pristine/observed 6/7). The study ran 18 compact configurations and six full replays; source snapshots are isolated, with only observable-module changes relative to their audited parents. No production kernel edits or paid cloud use. Archive readback and replay receipts accompany this checkpoint.

## Next step

Before efficacy sampling, qualify WAL recycling across cold diagonal adaptation. The existing observer was validated for fixed kernels; blindly treating warmup output as retained estimates would be wrong. Audit the discarded/retained boundary in walnutpie.rs, suppress auxiliary/warmup records without altering RNG or adaptation, and compare pristine/disabled/enabled retained draws, warmup work and final tuning. Keep the native cold controls and exact latent-coordinate controls. Then freeze a separate calibration/validation design with all warmup and tuning costs accounted for. The previously negative Gaussian branch remains closed; this target is a mechanism probe, not a practical use case.
