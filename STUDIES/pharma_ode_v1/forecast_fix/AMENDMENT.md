# Forecast numerical repair, before fresh validation

The initial full-concentration BDF forecast can cross zero numerically after
concentrations decay below absolute solver tolerance. Reproduced with a fixed
Laplace draw (index3911, subject1); independent DOP853 log-state continuation
returns final log concentration -19.4177664 while original BDF yields NaN.
This is not an inference-method failure or evidence for either sampler.

Change only generated predictions: compute the positive concentration at the
first observed time with the original solver, then integrate log concentration
with dlogC/dt=ka*D/V*exp(-ka*t-logC)-(Vm/V)/(Km+exp(logC)). No clipping or floors.
The training likelihood, gradients, priors, model, starts, seeds, budget,
selection and accuracy gates remain unchanged. Test against independent
integration and original likelihood/gradients. Audit retained points as before.
Forecast-only absolute/relative tolerances are min(training tolerance,1e-10).
An initial 1e-8 log-state preflight missed the independent prediction tolerance
by 1.69e-6 log units; tighten the forecast solver rather than relaxing the test.

Preserve initial02 as the failed forecast implementation; rerun all 53 jobs
under separately frozen source/build hashes, including successes. Do not tune
using its heldout scores. Worker now saves raw parameters before forecasting,
so any later forecast failure preserves the sampled draws. Successful full
draw archives replace that temporary duplicate. No outcome-based target drops.
Root: /home/ubuntu/lanes/pharma-ode-logforecast-20261029.
