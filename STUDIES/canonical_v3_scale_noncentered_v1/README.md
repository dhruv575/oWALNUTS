# canonical-v3 scale-non-centered study (WP17)

Preregistered study of a scale-non-centered innovation parameterization
(`canonical-v3`: `d_t = mu + sigma_x * eps_t`, log-Jacobian
`(T-1) log sigma_x`) against canonical-v2 in `a = 1` centered coordinates, on
the `sigma_x -> 0` funnel cell (`sspd-10`), the non-pathological T=1000 cell
(`sspd-11`), and the T=100 sanity cell (`sspd-05`), with a NumPyro NUTS
external reference on the v3 density (arm N3). Kernel
`walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10` at `d8617a8`; fresh seeds
95001–95003; zero-callback preflight for all 12 oWALNUTS cells
(`artifacts/owalnuts-v1/preflight.json`).

Protocol: `PREREGISTRATION.md`, `protocol.json` (frozen before sampling;
one post-sampling-crash interpreter deviation recorded, no result observed
before the rerun). Full tables: `artifacts/owalnuts-v1/results-table.md`;
machine-readable: `artifacts/owalnuts-v1/summary.json`.

## Verdict

**canonical-v3 is falsified as a general parameterization, on every fixture,
for every sampler tested — including the NumPyro reference.** The mechanism
is not the kernel: the v3 likelihood couples the `eps` block through the
cumulative sum, so its curvature scales like `sigma_x^2 T^2 c_t` (`c_t` the
observation curvature). Non-centering removes the `sigma_x -> 0` neck but
creates a mirror-image stiff region at moderate-to-large `sigma_x` — exactly
where informative data put the posterior, and where the shared start rule
puts every chain.

**The positive result is V2-A**: canonical-v2 (`a = 1`) with the JMLR
Appendix C adaptation passes every gate on `sspd-11` and `sspd-05` and is
**1.20× / 1.02×** more efficient (min bulk ESS per retained target call) than
the confirmed standard-adaptation arm V2-I — the first pass of paper
adaptation on the real T=1000 target.

`sspd-10` remains unsolved by every arm, now including both parameterizations
and the external reference.

## Results (gates: rank R-hat ≤ 1.01, bulk/tail ESS ≥ 400 on eight
functionals, zero retained div/invalid/exhaustion, caps ≤ 1%)

| fixture | arm | max R-hat | min bulk ESS | cap rate | median depth | retained work | wall s | min bulk ESS/work | gates |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| sspd-10 | N3 (NumPyro, v3, depth 12) | 3.269 | 4 | **100%** | 12 | 32.8M lf | 1,544 | 1.4e-07 | FAIL |
| sspd-10 | V2-I | 2.835 | 5 | 58.8% | 8 | 1.32M | 32 | 3.5e-06 | FAIL |
| sspd-10 | V3-D | 3.455 | 4 | 85.1% | 8 | 1.77M | 36 | 2.5e-06 | FAIL |
| sspd-10 | V3-A | — (frozen chains) | 4 | 0% | 1 | 2.05M | 29 | 2.0e-06 | FAIL (8,000/8,000 retained divergent+exhausted) |
| sspd-10 | V2-A | 2.167 | 5 | 40.2% | 5 | 0.99M | 26 | 5.2e-06 | FAIL |
| sspd-11 | N3 (v3) | 2.844 | 5 | 99.9% | 12 | 32.7M lf | 1,528 | 1.4e-07 | FAIL |
| sspd-11 | V2-I | 1.0011 | 841 | 0.74% | 8 | 1.73M | 35 | 4.9e-04 | **PASS** |
| sspd-11 | V3-D | 3.335 | 4 | 60.6% | 8 | 1.36M | 27 | 3.3e-06 | FAIL |
| sspd-11 | V3-A | — (frozen chains) | 4 | 0% | 1 | 2.05M | 23 | 2.0e-06 | FAIL |
| sspd-11 | **V2-A** | **1.0020** | **931** | **0.59%** | 8 | 1.59M | 32 | **5.9e-04** | **PASS** |
| sspd-05 | N3 (v3) | 1.0114 | 708 | 0% | 9 | 3.66M lf | 58 | 1.9e-04 | FAIL (R-hat, narrow) |
| sspd-05 | V2-I | 1.0040 | 582 | 0% | 5 | 0.30M | 1 | 1.9e-03 | **PASS** |
| sspd-05 | V3-D | 1.735 | 6 | 77.3% | 8 | 1.67M | 4 | 3.7e-06 | FAIL |
| sspd-05 | V3-A | 2.364 | 5 | 32.4% | 5 | 2.18M | 5 | 2.3e-06 | FAIL (1,998 exhaustions) |
| sspd-05 | V2-A | 1.0070 | 548 | 0% | 5 | 0.28M | 1 | 2.0e-03 | **PASS** |

Work units differ: oWALNUTS reports retained fused target calls, NumPyro its
`num_steps` leapfrog proxy; ESS/work is not cross-backend comparable.
Efficiency ratios (min bulk ESS per retained call): V2-A/V2-I = 1.49
(sspd-10), 1.20 (sspd-11), 1.02 (sspd-05); V3-D/V2-I = 0.0019–0.71;
V3-A/V3-D = 0.60–0.79.

## Predictions versus outcomes

| prediction | outcome |
|---|---|
| P1: v3 removes sspd-10 caps for V3-D; V2-I caps | **First clause falsified** (85% caps; chains never left the stiff `sigma_x ≈ 0.18` start region). Second clause held (58.8%). |
| P2: V3-A ≥ V3-D on ESS/call (sspd-10) | **Falsified** (0.79×; V3-A exhausted refinement on every retained transition and froze). |
| P3: N3 divergences < 151 | Held in letter (0), **but only because every trajectory hit the depth-12 cap instead**; the arm failed harder than the v2 reference in WP4b. |
| P4: V3-D passes health on sspd-11 with lower efficiency | **Health clause falsified** (60.6% caps; `sigma_x` wandered to ≈ 0.98 against a HalfNormal(0.1) prior — stuck chains, not posterior mass). |
| P5: V2-I and V3-D both pass and agree on sspd-05 | **Falsified for V3-D** (77.3% caps, R-hat 1.73). The v2/v3 same-posterior check is instead supported analytically (unit-tested Jacobian identity) and by N3's sspd-05 means agreeing with V2-I (max |z| = 1.96). |
| P6: V2-A keeps V2-I's health; does not remove sspd-10 caps | **Held** (and V2-A improved efficiency everywhere: 1.02–1.49×). |

## Refinement evidence (measured, per protocol)

On the centered target, Appendix C adaptation used its refinement levels
productively: V2-A on sspd-10 ran at median depth 5 (V2-I: 8) with 40% caps
versus 59% and 1.49× ESS/call; on sspd-11/05 it matched or beat V2-I with
identical health. On the v3 target refinement could not compensate: the
stiff region exceeded 8 halvings from `h = 0.1` and V3-A burned its exact
per-transition budget (`4 × 2,500 × 256` calls) without moving any chain.

## Why v3 fails (mechanism)

The latent path is `x_t = x_1 + (t-1) mu + sigma_x * cumsum(eps)`, so the
Gauss–Newton curvature of the likelihood in `eps` has top eigenvalue
`≈ sigma_x^2 · lambda_max(J' C J) ~ sigma_x^2 T^2 c`. At the shared start
(`sigma_x ≈ 0.18–1.0`) this is 10^4–10^8 for these fixtures, against a unit
prior scale: NUTS needs depth ≥ 9 at T=100 (N3 measured median 9) and
saturates depth 12 at T=1000. A `sigma_x`-dependent coordinate scale cannot
be fixed by any static metric or by within-orbit refinement at practical
budgets: the funnel has moved, not disappeared.

## Processor recommendation

Do **not** adopt canonical-v3. Keep `polyscope-canonical-v2` in `a = 1`
coordinates (WP12-confirmed arm I) as the production target, and adopt the
Appendix C warmup (V2-A configuration: `PaperAdaptationConfig(2.0, 0.95,
0.8)`, 8 refinement levels, depth 8) as the preferred adaptation once a
three-seed confirmation is run — it passed both healthy fixtures here with a
1.02–1.20× efficiency gain over dual averaging. `canonical.rs` needs no
change. For the `sigma_x -> 0` funnel cell the remaining candidates are
position-dependent geometry (e.g. a `sigma_x`-conditioned path block refresh)
or a *partial* scale non-centering `a_s ∈ (0,1)` chosen per market from the
data — not the full non-centering tested here; both require their own
preregistration.

## Reproduce

```powershell
cargo +1.88.0-x86_64-pc-windows-gnu test --release
cargo +1.88.0-x86_64-pc-windows-gnu run --release -- --preflight-only --out artifacts/owalnuts-check --kernel-commit <commit>
cargo +1.88.0-x86_64-pc-windows-gnu run --release -- --out artifacts/owalnuts-check --kernel-commit <commit>
C:\dev\polyscope\.venv-bench\Scripts\python.exe numpyro_reference.py --out artifacts/numpyro-check
python analyze.py --owalnuts artifacts/owalnuts-check --numpyro artifacts/numpyro-check
```

Raw functional draws (`artifacts/owalnuts-v1/draws/*.f64`,
`artifacts/numpyro/*.npy`) are hashed in `CHECKSUMS.sha256` and not
committed.
