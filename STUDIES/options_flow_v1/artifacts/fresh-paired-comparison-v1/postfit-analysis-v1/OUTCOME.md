# Frozen fresh-pair comparison outcome

All 72 intended fits completed and were usable. Both workflows passed the prospectively declared accuracy and reliability gates. The runtime superiority gate did **not** pass.

Public workflow: 2,709.680 seconds total, 75.269 seconds per successful workflow. Reference: 3,219.493 seconds total, 89.430 seconds per successful workflow. The reference/public cost-per-success ratio is 1.188; its separate approximate 95% paired-bootstrap interval is [1.069, 1.320]. The preregistered requirement was a lower endpoint above 1.25; the result does not satisfy that requirement.

Both arms completed 36/36. Each exact one-sided 97.5% completion-probability lower bound is 0.902606, giving the declared two-arm 95% reliability family on this fixed target. All 24 signed-mean and 24 RMS endpoint checks pass. Their complete intervals and observed point summaries are in summary.json; widths refer to the audited reference-bank W_low.

The limiting mean check is reference beta_bar_0.05: interval [-0.011006227140689266, 0.0034026172819011493], leaving 0.008994 W to its nearest ?0.02 W boundary. The limiting RMS check is public tau_0.95: upper 0.021188 W, leaving 0.018812 W below 0.04 W.

The 5,929.173-second workflow total includes all intended cell costs plus 0.016483 seconds shared terminal overhead allocated equally. Postfit verification and decision analysis required another 158.656 seconds, recorded separately; it is not sampler runtime. Source files were not edited and no fitting was rerun.

Reference-bank construction was a separate research-validation expense: 15,650.645 seconds fitting plus 2,556.239 seconds analysis (about 5.06 hours), excluding earlier setup. The workflow ratio does not charge this bank to either sampler. The bank is reused to evaluate this experiment, not assumed to be rebuilt by every production user; no amortized production saving including its construction is claimed.

This is repeatability on one demanding T1000/G4 posterior, not market calibration or general sampler qualification. Bank uncertainty and numerical envelopes are propagated, but bootstrap coverage and absence of shared missed-mode bias are not established. Accuracy, reliability, and runtime use separate confidence families, not one joint 95% statement. Independent terminal review remains separate.

Replay command is recorded exactly in execution.json. prepare_and_run.py records immutable postfit evidence; controller_transport.py was the frozen preregistered driver. All outputs are new files, and no prior failure/result was overwritten.
