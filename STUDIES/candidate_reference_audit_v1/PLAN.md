# E71: K400 versus extended references at the fixed 24 E66 points

Exploratory analysis of sealed E66 candidate score arrays and sealed E70
reference results. All 24 fixed points remain; the two failed E70 references
are explicitly flagged rather than silently treated as truth. No new sampling,
new data, candidate replacement, tuned threshold or qualification claim.

Verify source artifacts against both studies' manifests. Recompute candidate
mixture log density and PIT from stored chain/draw arrays; compare to saved
scores. Estimate candidate log-density delta-MCSE and PIT MCSE with the same
chain-aware ArviZ mean-MCSE method as the original reference evaluator. Record
signed candidate-minus-extended-reference discrepancies and each side's MCSE
separately. Do not turn MCSE into a stopping rule or treat 24 spot checks as a
whole-path accuracy guarantee. All-point and passing-reference-only summaries
are descriptive, explicitly distinguished. No selected-point claim of superiority.

This audit motivates a future fixed factorial budget/seed experiment if short
continuations dominate approximation uncertainty. A model-versus-EWMA advantage
does not identify an algorithm-specific improvement.
