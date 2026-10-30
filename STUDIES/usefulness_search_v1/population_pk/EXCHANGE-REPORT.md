# Population rate-exchange mechanism pilot

Status: completed; useful mixing mechanism, no demonstrated unique WALNUTS
advantage and no qualified posterior reference. Goal remains active.

Original tuned population pilots left both engines in their starting rate-order modes.
The secondary mode's local Laplace log-mass ratio (-21.87) is an approximation,
not a posterior mass bound. An exact involutive MH move exchanges absorption
and elimination rates with the corresponding volume transformation. Its priors
and nonzero-baseline likelihood are included in the acceptance ratio. This is
established model-aware Metropolis methodology, not new generic sampler theory.
See INVOLUTION-METHOD.md for derivation and literature.

52 numerical involution/Jacobian checks and an unequal-weight known-mixture
control passed. Separate retained-state/proposal audits tested 448 points per
engine against the archived Stan log density; offset ranges were 2.38e-7 (WALNUTS) and
1.40e-9 (NUTS), with no evaluation failures.

| Engine / mechanism | Worst R-hat | Minimum bulk ESS | Primary-mode fractions by chain | Calls | Seconds |
|---|---:|---:|---|---:|---:|
| WALNUTS plain | 1.742 | 7.63 | 1,0,1,0 | 2,762,916 | 95.52 |
| WALNUTS + exchanges | 1.062 | 58.82 | 1,1,1,1 | 2,582,650 | 86.61 |
| PyMC NUTS plain | 1.788 | 7.39 | 1,0,1,0 | 3,240,332 | 203.35 |
| PyMC NUTS + exchanges | 1.017 | 123.78 | 1,1,1,1 | 2,547,322 | 156.83 |

Each result retains only 40 chunk endpoints per chain after discarding 20 of
60 chunks, with 25 local transitions per chunk. Exchange arms each accepted two
global moves (one per secondary-started chain) and zero local moves. No return
crossings occurred. WALNUTS recorded zero divergences; NUTS recorded one in each
arm, not phase-separated. Neither engine hit the depth limit or recorded target
callback failures. Exchange density evaluations (960 per arm) are additional to
the tabulated local-kernel target calls. All four supervised jobs exited cleanly
within 300 seconds and 0.40 GB RSS; source manifests remained unchanged.

The NUTS timing uses a Python/PyTensor implementation and is not a fair native
engine efficiency comparison. The installed nutpie zero-warmup path panicked;
a one-warmup fixed-step workaround still initialized a state-dependent mass
matrix and was rejected. These implementation failures are preserved. An
isolated PyMC 5.28.2 control with explicit identity precision, no adaptation and
fixed step .05 passed native density/gradient parity checks before use. Both
engines received the same MH schedule, starts, whitening and chunk lengths.

All three completed batches have private S3 exact-version restore and per-member
hash verification: pilot_archive (41 members), jump_archive (48 members), and
pymc_archive (834 members, including the isolated control environment). Original
EC2 files remain. JSON reports are checked in; archives remain outside Git.

Follow-up completed: see QUALIFIED-REPORT.md. Source inspection corrected an
assumption in the initial plan: the linear branch already used a closed-form
curve inside Stan. The new C++ gradient removes per-subject autodiff overhead;
it does not remove numerical ODE solves from the linear model. The longer
reference qualifies, but matched native NUTS is more efficient than WALNUTS.
