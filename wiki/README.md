# oWALNUTS wiki

The record of what was tried, what worked, what did not, and why. Start with
the synthesis pages; go to the ledger for the numbers behind any claim.

## Start here

- [Decisions register](decisions.md): every default change and every
  rejected default candidate, with the study and the reason.
- [Negative results](negative-results.md): the catalogue of things that did
  not work, so they are not rerun.
- [Open questions](open-questions.md): what is still unmeasured, ranked.
- [Methods](methods.md): how a study is run here (preregistration, seeds,
  gates, bit-identity, artifacts, environment pitfalls).
- [Studies index](studies-index.md): one row per `STUDIES/` directory.

## Findings by topic

Each page has the same shape: state of knowledge, timeline of evidence,
what worked, what did not work, current default, open questions.

- [Benchmarks](findings/benchmarks.md): the posteriordb v1 to v6 series,
  Eight Schools, the funnel, NumPyro and crypto comparisons, and the honest
  position.
- [Step size and warmup adaptation](findings/step-size-adaptation.md): dual
  averaging, the paper's Appendix C rule, exhaustion rules, and the WP40
  warmup-gap diagnosis.
- [Mass metric](findings/mass-metric.md): the regularisation floor, the
  joint default, and structured path metrics.
- [Orbit selection and U-turn](findings/orbit-selection-and-uturn.md):
  biased progressive selection, `MomentumSum`, endpoint rules.
- [Refinement and reverse coarsening](findings/refinement-and-reverse-coarsening.md):
  levels, delta, reverse-check order and policy, the truncation hypothesis.
- [Chain rescue](findings/chain-rescue.md): warmup-time restart and pooling,
  adopted then withdrawn.
- [Kernel correctness](findings/kernel-correctness.md): v8 to v10
  corrections, oracles, fingerprints.
- [State-space targets](findings/state-space-targets.md): sspd fixtures,
  parameterisations, crypto stochastic volatility.
- [Integrations and platforms](findings/integrations-and-platforms.md):
  BridgeStan, PyMC and Python transport, Windows native faults, publishing.

## Primary records

- [Research ledger](research-ledger-2026-08-31.md): one append-only,
  checksummed entry per study (WP2 to WP40). The source of every number.
- [Research programme 2026-09-04](research-program-2026-09-04.md): the 0.2
  programme as it stood at release.
- [Release 0.2.0](release-0.2.0.md): release notes, validation tables,
  limitations.

## History

Earlier documents kept at their original paths because other files link to
them. They describe the state at the time and are superseded by the pages
above where they disagree.

- [Research programme 2026-08-31](research-program-2026-08-31.md): the
  programme that produced 0.1.0-beta.2.
- [Release 0.1.0-beta.2](release-0.1.0-beta.2.md): includes the Eight
  Schools erratum.
- [Sampler path ledger](sampler-path-ledger.md) and
  [sampler path redesign](sampler-path-redesign.md): the pre-0.1 state-space
  path work.
- [nextstat 0.10.1 clean-room study](nextstat-0.10.1-clean-room-study.md).

## Conventions

Synthesis pages cite the ledger by WP code and the study by `STUDIES/<dir>`.
A number that appears on a synthesis page must appear in the ledger or a
study README. Synthesis pages are edited as knowledge changes; the ledger is
never edited, only appended.
