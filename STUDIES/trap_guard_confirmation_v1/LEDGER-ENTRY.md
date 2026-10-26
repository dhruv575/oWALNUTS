### WP90-TRAP-GUARD-CONFIRMATION-V1: the WP67 restart rule at step ratio 0.01 (`guard-0.01-0`) qualifies by every frozen rule on 22 v7 posteriors x 6 fresh seeds, the funnel and the SV model (92 = 92 gates, 282/282 bit-identical pairs, headline 1.0000, funnel 0 firings, SV 8/480 -> 0/480, 0 false firings), and is proposed for the flip; two `kilpisjarvi` firings on chains that would have recovered are a caveat the rules did not anticipate

- **When and where.** 2026-10-26 on `wt/trap-guard-confirm`, preregistered at `d71fc639` (harness
  `df1b9047`, base `main` `f5500db3`, no library change). Lane 1 of the shared box (pinned, co-tenanted),
  21:11-22:49 UTC; 564/564 cells, none rerun, no errors. Smoke on seed 9059901 disclosed before the
  freeze.
- **Protocol.** `STUDIES/trap_guard_confirmation_v1/{PREREGISTRATION.md,protocol.json}`. Candidate:
  `with_trapped_chain_restart(step_rule().with_step_ratio(0.01).with_check_window(0))` as
  `Adaptation::Custom` of the sampler's own warmup defaults, unchanged from WP89. Part 1: 22 v7
  posteriors x seeds 9050101-9050106 x {defaults, guard} at 4 x 1,000/1,000 (WP85 gates and tiers);
  Part 2: funnel 4 x 2,000/20,000, seeds 9080301-9080330; Part 3: WP84 SV model, seeds 9090101-9090220,
  WP89 census with WP89's anchor. Rules R1-R8 conjunctive; trapped-at-the-defaults for the firing audit
  = warnings (T1) or > 3 reference SD (T2) or the WP89 signature at transition 99 (T3: step ratio < 0.01
  and log density more than 3 median IQR below the retained reference).
- **Outcome.** R1 92 = 92 of 132; R2 282/282 (268 unfired cells identical, 14 fired cells' untouched
  chains identical); R3 0 new divergences; R4 1.0000 (2 of 132 pairs off 1: 0.979, 1.0025); R5 funnel
  P5 0.04579 +- 0.00159 (1.26 s.e. from exact), 30/30 identical, 0 firings, lowest healthy ratio 0.066;
  R6 SV guard 0/480 against defaults 8/480 (7 cells; WP89 8/480), 13 firings = 8 traps + 5 near-traps,
  every restarted chain at the mode, 0.88x the defaults' target calls; R7 2 Part 1 firings
  (`kilpisjarvi` 9050101 c1 ratio 0.0092, 9050106 c0 ratio 0.0063), both T3-true, 0 false by the frozen
  definition; R8 fingerprint 3 + 3, restart tests 5, clippy clean, diff empty. Predictions P3-P7 held;
  P1 (firings only on lotka / GLMM) and P2 (defaults passes 98-112; observed 92, identical in both arms)
  did not.
- **Caveat.** The two `kilpisjarvi` firings (3-D, slow identity-phase warmup, step ratios at the window
  close dispersed from 0.006 to 72 over six cells) were on the *best-placed* chain of the four at
  transition 99 (371 / 484 nats above the chain median; no chain near the typical set yet); at the
  defaults both recovered. They satisfy T3 only because every chain was far below the retained
  reference there. Cost nil: gates unchanged (both cells fail on other chains in both arms), gradients
  0.991x / 1.027x, restarted chains at the mode. Rate 2 of 1,056 Part 1 chains.
- **Decision.** QUALIFIES; `guard-0.01-0` proposed for the flip (`protocol.json` `proposed_flip`:
  `TrappedChainRestartConfig::guard()`, `DEFAULT_TRAPPED_CHAIN_RESTART` installed where
  `DEFAULT_CHAIN_RESCUE` would be, research gate lifted, `ALGORITHM_REVISION` and fingerprints unchanged,
  Python no signature change). Applied by the coordinator, with the caveat above on record.
- **Next.** If the caveat matters: a two-signal variant (step ratio and log density below the chain
  median at the window close) would not have fired on `kilpisjarvi` and would have fired on all 13 SV
  chains; it needs its own preregistration. The gradient-scaled initial metric (WP89's `nutpie_init`)
  remains the cause-side fix.
