# WP79 `metric_autoselect_v2`

**Verdict: PROPOSE (for a default-flip confirmation; research flag only).**

- Library: `cac8c704` (`DenseAutoSelectConfig::hessian_fit`, diagonal facade).
- Harness: `aa2af6a6` / `6f888207`.

**Setup:** 17 models x 3 seeds (797501-797503) x diag / dense / auto, plus
funnel x 10 seeds (797401-797410). AWS lane 3, `taskset -c 8-11`.

**Rules:**

- **R1:** 44 vs 44.
- **R2:** geomean 2.20.
- **R3:** no model below 0.9x.
- **R4:** 0 new divergences.
- **R5:** 43/43 diagonal-branch cells are bit-identical to diag.
- **F:** P5 0.0482 ± 0.0019.
- **D:** holds.

**Predictions:**

- **Held:** A1, B1 (the GP guard), B3, B4, B5 and Pb.
- **Failed:** Pa, 45 of 51 against 48 needed. The 6 misses are earnings and
  kidiq going diagonal on every seed, which also fails B2.
- **Why:** in-run linearity was 0.002-0.32, against 0.99 on retained draws.
- **Status:** the earnings miss is accepted, not fixed.
