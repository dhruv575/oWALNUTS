# Independent demanding-calibration design review

Reviewed DRAFT.md, planning.py, test_planning.py and planning-results.json in
target/demanding-calibration-design-v1, plus the actual model.simulate,
model.functionals and dispersed_starts implementations. No sampling or seeds
were selected by this review.

## Verdict

Proceed to a bounded, explicitly exploratory T1000/G4 resource screen after
resolving the family/estimand mismatch below. Do not freeze a confirmatory sample
size from the present power table: its arithmetic is appropriate for a stronger
worst-case-completion criterion than the first definition in the draft.

## One material statistical correction before freeze

The prose defines 37 simultaneous intervals as 18 conditional coverages,
18 usable-and-covering probabilities and one usability probability. The code
instead allocates to 18 lower bounds for H/N, 18 upper bounds for (H+F)/N,
and one reliability lower bound. These are different families and different
primary claims. A qualification rule need not require worst-case completion
coverage merely because failures exist.

Choose prospectively between:

* **Production-output coverage:** simultaneous conditional coverage equivalence
  plus reliability, with usable-and-covering also reported in the declared
  37-interval family. Worst-case failed-output bounds are sensitivity results;
  they do not receive an undeclared simultaneous confidence guarantee.
* **Robust completion sensitivity:** the code's H-lower/U-upper/reliability
  family, explicitly stronger. Conditional intervals are descriptive or have
  separately declared error allocation. This asks whether every possible
  coverage assignment to absent outputs would satisfy the margin; it does not
  discover an actual interval for a failed computation.

If all conditional, H and U intervals plus reliability are claimed jointly,
there are 55 intervals, not 37. Alternatively allocate error directly among
the exact one-sided claims needed. The current alpha/(2*37) tails are
conservative for 37 one-sided robust-completion claims, not incorrect.

## Power arithmetic and interpretation

For independent generated datasets with usability probability s and conditional
coverage c, H is Binomial(N,s*c), U=H+F is Binomial(N,1-s+s*c), and S is
Binomial(N,s). The code's marginal acceptance sums and union bound
max(0,1-18*((1-P_lower)+(1-P_upper))-(1-P_reliability)) are valid conservative
power bounds without assuming independence across selectors. The reported
minimum N is the first integer meeting this **lower bound**, not the exact
minimum for 80% joint power. Positive dependence can make actual joint power
higher. At s=1, the per-selector robust rule reduces to ordinary equivalence.

The reported N=1328/1624/2026/3430 for s=1/.995/.99/.98 are thus scenario
calculations for the robust rule, not user requirements. The selected scenarios
fix c=.90; add the promised .85/.875/.925/.95 sensitivity before choosing a
confirmatory N. Sample sizes at nominal power do not establish power for
near-margin alternatives. A failure of equivalence is inconclusive evidence
unless the confidence bounds demonstrate a directional departure.

For the conditional-output design, do not substitute floor(N*s) for random S.
Integrate exact acceptance over S: sum_s BinomialPMF(s;N,p_usable) times
the binomial acceptance probability conditional on s usable cases. The present
floor-expected-count diagnostic is correctly labeled only a diagnostic. A
dependence-robust joint power lower bound can then combine the 18 marginal
conditional-rule failure probabilities and reliability failure probability.

Global-budget truncation needs special treatment. Unstarted queue positions
are not iid per-fit computational failures: admission depends on preceding
costs. Preserve all intended cases, but label a confirmatory campaign with any
unstarted case unresolved. Do not claim exact fixed-N binomial coverage by
coding unstarted cases as zero, nor exact fixed-n coverage for an
outcome-dependent completed prefix. Independently applied per-fit timeouts are
part of the fixed procedure and may legitimately contribute failed outcomes.

## Generative and algorithmic scope

The actual simulator draws all four global priors, group effects, stationary
AR(1) initial state/transitions and Student-t observations consistently with the
target, at rho=.95 and nu=5. The forecast generates a new latent state and new
observation noise. Truth for h_terminal/h_mean must use only the first1000
states; forecast truth is the generated observed y, not its latent mean.
The 14+4 selectors are dependent within a dataset but each has one trial per
independent dataset. T1000/G4 gives1012 canonical coordinates; preserve the
whole health gate even though coverage examines18 scientifically named outputs.

dispersed_starts uses shape, fixed rho and a separate seed, not y, x or truth.
It is suitable as the unchanged production initialization. Add an explicit
mutation regression: changing truth and held-out y must not change starts,
sampling target, stopping policy or preselected reference membership. Share
the physical matrix with the paired reference, not sampler/prediction streams.

The primary target is repeated-dataset coverage of the **finite production
algorithm's output**, including its stopping and predictive simulation. Exact
posterior sampling is not required to measure that quantity. Exact binomial
intervals refer to repeated independent datasets, not exact MCMC. Passing does
not prove posterior closeness on every dataset, conditional frequentist
coverage at fixed parameters, real-market adequacy or an iid SBC-rank law.

## Concrete next executable resource screen

Freeze 32 fresh prior-generated T1000/G4 public cases and eight reference cases
at indices0,4,8,12,16,20,24,28 before generation. Retain the current exact public
and associative mixed reference recipes, starts policy and first-pass gates.
Interleave each selected reference with its public case and alternate which
backend is first across the eight pairs. Freeze all40 IDs/stream roles first.

A proposed six-hour admission budget,1800 seconds per contained worker and
15-second cleanup reserve is a clear bounded screen. The fixed-target means
suggest roughly52 minutes for32+8, but are not prior-predictive cost estimates.
The per-worker worst-case sum is20 hours; therefore six hours explicitly allows
unstarted cases, all retained descriptively. No retries, replacement priors,
truth-selected starts, coverage-dependent stopping or relaxed gates. Stop on
integrity/containment failure; ordinary fit failures remain results.

Freeze a storage cap and pre-run admission estimate after a transport smoke.
Keep canonical data losslessly if changing storage, with exact round-trip and
current-adapter tests before freeze. Charge compilation, parity, all tiers,
diagnostics, prediction, hashing and serialization. Record endpoint/truth
distances and MCSE sensitivity without changing primary interval endpoints.

Progression to confirmation requires intact source/provenance and all40
statuses, no unresolved transport defect, complete18-selector truth extraction,
and credible measured resource capacity for the chosen confirmatory design.
Failures may motivate algorithm development, but then confirmation uses new
datasets and the frozen revised procedure. Do not tune on the screen and pool
it into confirmation. Choose the final estimand, margins, reliability rule,
family allocation and N from prospective power/resource requirements, preserving
negative findings. The screen itself cannot qualify95% reliability or18-way
coverage equivalence; it answers whether the demanding procedure is ready for
that experiment.
