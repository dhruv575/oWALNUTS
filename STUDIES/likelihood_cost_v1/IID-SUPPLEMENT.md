# Analytic IID control, specified before inspecting main outcomes

The main 80-fit protocol remains unchanged. Because this controlled regression
has an analytic posterior, add 16 exact IID control cases: eight seeds per
observation size, four independent chains of 6,000 draws mapped into original
q coordinates. Use identical exact error/MCSE and R-hat/ESS gates. Preserve
draws and report setup, draw generation and diagnostics separately. This is
the strongest available optimized baseline, and avoids implying that a NUTS
reparameterization is the best way to solve conjugate Gaussian regression.
Seeds805000000+case*1000+rep. The supplemental process amortizes imports across
cases; do not compare its per-case cost with cold worker totals without noting
this. No changes to the full-evaluator mechanism success criterion.
