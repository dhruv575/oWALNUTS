# Calibration and algorithm attribution: design notes

Status: proposed follow-up, not a frozen experiment or a result. E72 remains
the active campaign. No additional CPU sampling is co-scheduled on its cores.

## Prior work and what it rules out

WALNUTS already includes stochastic-volatility experiments, so applying its
transition to SV is not itself our novel contribution. Attribution belongs to
Bou-Rabee, Carpenter, Kleppe and Liu, [JMLR 27(113), 2026](https://www.jmlr.org/beta/papers/v27/25-1452.html).

Wee's [2024 master's thesis](https://arxiv.org/html/2402.12384v1) compares NUTS
and an offset-mixture approach with simulation-based calibration. Its model
has Gaussian observation noise and unknown persistence, unlike our fixed-rho
Student-t observation model. Its findings therefore cannot rank the algorithms
for our target. It also makes an SV calibration comparison alone insufficient
as an originality claim for our work.

## Proposed question

Does repeated finite-budget warm continuation preserve useful posterior
calibration over changing rolling-window targets, at lower measured cost than
independent refits of exactly the same model? E72 addresses budget sensitivity
at reference spots, not this full question.

Generate each synthetic history from the exact prior and stationary latent
process used by the implementation. Draw global parameters once per history,
then generate a continuous latent path and Student-t observations. Each rolling
window has the intended marginal generative model. Keep initialization history
and warm remapping exactly aligned with the deployed research implementation.
Freeze the path lengths and diagnostic tick positions before simulation.

At each fixed tick, compare posterior inference with the generating global
parameters and terminal latent state. Use independent simulated histories as
replication units. Multiple ticks in a history are correlated; do not count
them as independent SBC replicates. A marginal calibration assessment at each
fixed tick can use histories as its denominator, with an explicitly chosen
multiple-comparison or simultaneous-band procedure.

Raw ranks from autocorrelated chain draws do not automatically have the
independent-draw rank null distribution. The protocol must settle dependence
handling before claiming calibration: an ESS-derived thinning rule is not a
proof of independent draws. A development stage should test the diagnostic on
an exactly sampleable target, with deliberately correlated and deliberately
biased chains as controls. Report failures and low effective sample sizes;
do not discard difficult histories to improve rank plots.

Include data-dependent predictive functionals as well as parameter marginals.
Prior-like output can look marginally calibrated while ignoring observations;
the checks must be capable of detecting that failure. References and SBC are
complementary diagnostics, not certificates of finite-chain exactness.

## Comparator and cost requirements

Use the same likelihood, priors, precision and parameterization for the
candidate and independent NUTS refits. A specialized SV competitor may require
a Student-t augmentation or exact correction; a Gaussian approximation must
not be silently called the same target. Track development separately from
frozen evaluation, all initialization and adaptation costs, compilation costs,
retained output, end-to-end time and total CPU seconds. Measure performance
at comparable observed precision and retain unsuccessful attempts.

No speed claim follows from K400 versus K1600 alone: both use the same sampler.
No economic claim follows from synthetic calibration. The existing economic
accounting oracle still requires a feasible information, action and execution
model before a profitability experiment can be interpreted.

## Before freezing a campaign

1. Audit existing synthetic SV studies and reuse validated target/generator
   components where they match exactly; avoid duplicating an existing result.
2. Verify generative parameters, stationary initialization, indexing and the
   likelihood against independent calculations and small exact controls.
3. Choose diagnostics that detect both biased chains and ignored data, with
   dependence-aware uncertainty and explicit failure denominators.
4. Pilot runtime on declared development seeds, reserve new scientific seeds,
   choose a feasible fixed replication count, and set resource caps.
5. Freeze source, environment, data-generation law, comparisons and reporting
   before the scientific run. Do not tune the new protocol to E72 outcomes.
