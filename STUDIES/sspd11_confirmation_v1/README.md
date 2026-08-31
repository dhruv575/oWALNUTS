# sspd-11 confirmation on kernel v10 (WP12)

Preregistered fresh-seed confirmation of WP4b's arms **I** (a=1 centered,
adapted diagonal) and **P** (a=1, fixed posterior-precision tridiagonal path
block + fixed globals diagonal from arm I) on the non-pathological T=1000
fixture `sspd-11`, kernel `walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10`
at HEAD `93ed8e9`; plus a three-seed robustness check of WP10's Stock–Watson
arm A. Protocol: `PREREGISTRATION.md`, `primary/protocol.json`,
`stock_watson/protocol.json` (frozen before sampling). Post-processing:
`analyze.py` → `artifacts/summary.json`, `artifacts/RESULTS.md`.

```powershell
cd primary;       cargo +1.88.0-x86_64-pc-windows-gnu run --release -- --fixtures sspd-11 --arms I,P --out artifacts/primary-v1 --kernel-commit <sha>
cd ../stock_watson; cargo +1.88.0-x86_64-pc-windows-gnu run --release -- --preflight artifacts/preflight.json
                    cargo +1.88.0-x86_64-pc-windows-gnu run --release -- --sample A1 artifacts/A1.json   # A2, A3
cd ..; $env:PYTHONIOENCODING="utf-8"; python analyze.py; python checksums.py
```

## Primary — sspd-11, seeds 91001–91003 (4 chains, 500 / 2,000, depth 8)

| seed | arm | max R-hat | min bulk ESS | min tail ESS | div/inv/exh | cap rate | median depth | retained calls | wall s | min bulk ESS/call | max \|z\| vs I | max \|z\| vs N | run gates | confirmed-run |
|---:|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| 91001 | I | 1.0066 | 931 | 2119 | 0/0/0 | 0.0040 | 8 | 1,836,230 | 28 | 5.07e-04 | | 1.83 | PASS | yes |
| 91001 | P | **1.0102** (`beta`) | 691 | 624 | 0/0/0 | 0.0001 | 6 | 529,147 | 9 | 1.31e-03 | 1.86 | 1.25 | **FAIL** | no |
| 91002 | I | 1.0072 | 962 | 1884 | 0/0/0 | 0.0061 | 8 | 1,845,443 | 25 | 5.22e-04 | | 0.89 | PASS | yes |
| 91002 | P | 1.0070 | 697 | 962 | 0/0/0 | 0.0004 | 6 | 451,040 | 7 | 1.55e-03 | 1.66 | 1.63 | PASS | yes |
| 91003 | I | 1.0035 | 919 | 1714 | 0/0/0 | 0.0039 | 8 | 1,792,193 | 24 | 5.13e-04 | | 1.46 | PASS | yes |
| 91003 | P | 1.0058 | 740 | 776 | 0/0/0 | 0.0005 | 6 | 538,252 | 9 | 1.38e-03 | 1.92 | 1.43 | PASS | yes |

Every preflight started zero target callbacks; no wall cap was hit; no
deviation from the preregistration occurred.

* **Arm I: confirmed (3/3).** Max R-hat 1.0035–1.0072, min bulk ESS
  919–962, min tail 1,714–2,119, zero divergences / invalid stops /
  exhaustions, cap rate 0.39–0.61% (all ≤ 1%), median depth 8, and every
  functional mean within 1.83 combined MCSE of the NumPyro reference.
* **Arm P: not confirmed (2/3).** Seeds 91002 and 91003 pass every gate.
  Seed 91001 fails the R-hat gate on one functional, `beta`
  (rank R-hat 1.0102 vs the 1.01 limit; its bulk ESS 843 and tail ESS 624
  pass), while all seven other functionals are at ≤ 1.0040 and all health,
  cap and agreement gates pass (max |z| 1.86 vs I, 1.25 vs N). The
  confirmation rule is conjunctive and is applied as written.
* **Efficiency (reported, not gated):** min-bulk-ESS per retained target
  call, P/I = 2.573, 2.963, 2.683; geometric mean **2.735**, range
  [2.57, 2.96]. Wall 7–9 s (P) vs 24–28 s (I); NumPyro reference 47 s.
* Posterior agreement held everywhere: P vs I |z| ≤ 1.92, P vs N |z| ≤ 1.63,
  I vs N |z| ≤ 1.83 on all eight functionals and all seeds.

Predictions: P confirmed 3/3 — **failed**; I confirmed 3/3 — held; P/I ≥ 2 —
held; agreement on every seed — held; depth (P 6, I 8 with cap ≤ 1%) — held.

Reference: WP4b NumPyro NUTS, a=1, seed 86001, depth 12, 1,000 / 2,000
(`STUDIES/real_target_path_metric_v1/artifacts/numpyro/sspd-11-N-a1-86001.json`,
SHA-256 `e8587b3d…63cd6`; functionals `.npy` `5fe68ed7…376ee`; recomputed
with ArviZ 1.3.0 / NumPy 2.5.2).

## Secondary — Stock–Watson arm A, seeds 91011–91013

WP10's arm A (Appendix C adaptation, paper-mode v3 defaults, natural
recoverable errors) re-run on three fresh seeds with everything else
identical to `STUDIES/invalid_evaluation_parity_v1/stock_watson`.

| arm | seed | max R-hat (gated) | min bulk ESS | min tail ESS | div/inv/exh | cap rate | calls | wall s | final δ / h per chain | gates |
|---|---:|---:|---:|---:|---|---:|---:|---:|---|---|
| A1 | 91011 | 1.0074 | 592 | 1287 | 0/0/0 | 0 | 2,554,616 | 9 | 0.333/0.0061; 0.374/0.0066; 0.292/0.0065; 0.264/0.0070 | PASS |
| A2 | 91012 | 1.0071 | 463 | 796 | 0/0/0 | 0 | 2,494,088 | 9 | 0.243/0.0060; 0.305/0.0069; 0.283/0.0063; 0.286/0.0061 | PASS |
| A3 | 91013 | **1.0101** (`log_sigma2`) | 484 | 527 | 0/0/0 | 0 | 2,312,864 | 10 | 0.278/0.0069; 0.302/0.0063; 0.266/0.0065; 0.329/0.0069 | FAIL |

Pass rate **2/3**; gated max R-hat per seed 1.0074, 1.0071, 1.0101. Health
is clean on every seed (zero divergences, invalid stops, exhaustions, depth
caps); adaptation lands at δ ≈ 0.24–0.37 (paper 0.3) and h ≈ 0.0060–0.0070
on every chain. The non-gated reported functionals `z_1`, `z_mean`, `x_mean`
have R-hat 1.006–1.027 and bulk ESS 208–367, i.e. this fixture at 4×2,000
draws sits close to the R-hat limit for slow latent-mean functionals in
every seed; the WP10 miss (1.0101 on seed 90021) is therefore a run-length
effect at this draw count, not a seed-specific pathology.

## Verdict

* **Arm I (centered adapted diagonal) is confirmed** on sspd-11: the
  product-facing claim "oWALNUTS samples the canonical-v2 T=1000 target in
  a=1 coordinates with a plain adapted diagonal, passing modern gates at
  depth 8 on 3/3 fresh seeds, agreeing with NumPyro NUTS" is supported.
* **Arm P (posterior-precision path block) is not confirmed** by the
  conjunctive rule: 2/3, with a single-functional R-hat miss of 0.0002 on
  the third seed while every health, cap, ESS and agreement gate passed on
  all three seeds. The ≈2.7× ESS-per-call advantage over I is stable across
  seeds (range 2.57–2.96) and the posterior agrees with both I and NumPyro.
  What this supports: P is a healthy, unbiased and materially more efficient
  metric on this target; what it does not support: a claim that P passes the
  strict 1.01 R-hat gate on every seed at 500 / 2,000. A confirmation at
  4×4,000 retained draws (or with the path block refreshed at slow-window
  boundaries, as WP4b recommended) is the next preregistration, not a gate
  change.

No source was modified. Raw functional draws are hashed in
`CHECKSUMS.sha256` and not committed.
