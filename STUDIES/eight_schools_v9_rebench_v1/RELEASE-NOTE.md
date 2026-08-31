# Draft release note / erratum (Eight Schools throughput after the v9 correction)

**Correction.** Kernel revision v9 fixes a reversibility defect in oWALNUTS's micro-step
acceptance: acceptance was decided on the path-wide maximum energy error over all visited
micro-steps instead of the endpoint error `|H(end) − H(start)|` used by the reference
implementation. The path-wide statistic is not symmetric under time reversal, so leaves
that the reverse selection would have rejected were accepted. On Neal's funnel at the
paper's tuning this over-weighted the neck (P(ω < −5) = 0.097 versus the exact 0.048); v9
matches 4,000 reference funnel leaves to 1e-11 and reproduces the exact marginal
(0.0474 ± 0.0090). Every prior result from a refinement-active run is provisional until
re-run on v9. The frozen default tuning never reached a leaf where the two statistics
differ, so default-configuration outputs are bit-identical.

**Re-measured Eight Schools numbers.** On the v38 noncentered Eight Schools strict track
(four sequential chains, 1,000 warmup + 1,000 retained, target acceptance .95, depth 8,
adapted diagonal metric, one thread, warm sampler-call timing), v9 re-measured on the four
v38 seeds plus three fresh seeds gives a conservative minimum over all seven seeds and six
functionals of **12,830 bulk / 10,346 tail ESS/s**, with health and posterior agreement
gates passed on every cell. Paired ESS per target call is unchanged within noise
(geometric mean v9/v7: 0.96 bulk, 0.99 tail). These walls were measured on a loaded
machine and are conservative.

**Erratum on the previously published figure.** The 19,054.65 / 14,494.34 ESS/s reported
as oWALNUTS's "conservative minimum across seeds and six functionals" was in fact the
minimum over functionals of the across-seed *median*; competitor figures in the same
table were true minima over all cells. The like-for-like v7 minimum was 8,634 / 5,949
ESS/s (one seed had a 0.255 s wall against 0.09–0.11 s for the others). The qualitative
claim — fastest among the strict matched competitors tested locally (CmdStan 6,290 /
3,951; BlackJAX 5,645 / 4,195; NumPyro 5,241 / 4,050) — holds under both the old v7
minimum (1.37× / 1.42×) and the v9 re-measurement (2.04× / 2.47×), but the previously
stated margin was overstated and the aggregation mislabelled. NextStat remains faster
observed on its non-strict public-API track; no global-best claim is made.
