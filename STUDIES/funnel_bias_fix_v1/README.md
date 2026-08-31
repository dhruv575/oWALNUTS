# funnel_bias_fix_v1 — statistical proof of the v9 endpoint-criterion correction

Evidence class: preregistered regression check of a kernel correction against
an exactly known marginal; fresh seeds; executed 2026-08-31. Companion to
`paper_funnel_reproduction_v1` (WP2), which measured the defect, and to the
4,000-leaf differential oracle `oracle/walnutpie/f5bba365_funnel_leaves`,
which localizes it.

## Defect

Kernel revisions through `v8` accepted a refinement level when the largest
Hamiltonian departure of *any* visited micro-step from the start state was
within `max_error`. Measured from the endpoint the same path has different
departures, so the statistic is not symmetric under time reversal; the
deterministic reverse selection could disagree with the forward selection and
the kernel accepted non-reversible leaves. Upstream `walnutpie::macro_step`
decides on `|H(end) − H(start)|` only (`within_tolerance`, "only tests one
way"), which is symmetric. Against the unmodified upstream headers, 1,555 of
4,000 funnel leaves disagreed under `v8`; zero disagree under `v9`.

## Result under `v9` (`walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v9`)

Same target, starts, tuning, and gates as WP2 (10-D Neal funnel, h = 0.36,
δ = 0.21, 10 levels, depth 10, identity mass). Chain `i` uses `base_seed + i`.

| arm | seeds | draws | R-hat ω / x₁ | bulk/tail ESS ω | mean ω (MCSE) | var ω (exact 9) | P(ω<−5) obs / exact (z) | P(ω<−6) obs / exact (z) | q1% / q0.5% (exact −6.98 / −7.73) | div / invalid / exhaust / depth-cap | calls | wall |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **F50 (primary)** | 85001–85004 | 4×50,000 | 1.0016 / 1.0010 | 1,644 / 2,134 | +0.041 (0.074) | **9.04** | **0.0474 / 0.0478 (−0.08)** | **0.0223 / 0.0228 (−0.14)** | −7.01 / −7.84 | 0 / 0 / 0 / 43 | 8,209,439 | 4.1 s |
| F | 85101–85104 | 4×10,000 | 1.0056 / 1.0037 | 416 / 622 | −0.054 (0.144) | 8.63 | 0.0453 / 0.0478 (−0.29) | 0.0199 / 0.0228 (−0.47) | −6.68 / −7.24 | 0 / 0 / 0 / 0 | 1,774,245 | 0.9 s |
| WP2 F50 (`v8`, for reference) | 81101–81104 | 4×50,000 | 1.0053 / 1.0040 | 1,162 / 2,147 | −0.434 (0.099) | 11.41 | 0.0971 / 0.0478 (+10.7) | 0.0557 / 0.0228 (+10.2) | −8.24 / −9.02 | 0 / 0 / 17 / 64 | 12,770,697 | 7.4 s |

Per-chain P(ω<−5) for F50: 0.067, 0.036, 0.050, 0.037 (WP2 `v8`: 0.099,
0.082, 0.102, 0.106).

Primary gates (PREREGISTRATION.md): |ΔP(ω<−5)| = 0.0004 ≤ 0.009 ✔;
|ΔP(ω<−6)| = 0.0005 ≤ 0.006 ✔; var(ω) = 9.04 ∈ [8.2, 9.8] ✔; zero retained
divergences ✔. WP2's convergence gates also pass at both budgets. Retained
refinement exhaustions fell from 17 to 0 and target calls from 12.8M to 8.2M
at the same draw count; retained refinement-level histogram for F50 is
`[75184, 64057, 28196, 10797, 4110, 1737, 531, 113, 35, 7, 0]`.

Regression checks (`artifacts/gaussian-summary.json`,
`artifacts/eight-schools-regression-summary.json`):

* Arm G, 10-D standard Gaussian at the same tuning (seeds 85201–85204,
  4×10,000): mean z 0.16 / −0.29, variance 1.012 / 1.001, P(x<−2) z 0.98 /
  −0.50 for x₀ / x₁; zero health events; 636,306 calls.
* Eight Schools seed 82001 (WP3 runner copied verbatim, both arms): all health
  gates pass under `v9` (max R-hat 1.0020 / 1.0026, min bulk ESS 1,907 /
  1,233, zero divergences or depth caps). Geometric-mean bulk ESS per call
  `v9`/`v8`: 0.84 (BPS), 0.91 (multinomial); tail 0.88 / 0.96. One seed of
  1,000 retained draws has roughly ±10% ESS noise, so this is reported, not
  interpreted; BPS remains ahead of multinomial by 1.41× under `v9`.

## Reproduce

```powershell
cargo +1.88.0-x86_64-pc-windows-gnu build --release
.\target\release\funnel-bias-fix-v1.exe --preflight artifacts\preflight.json
.\target\release\funnel-bias-fix-v1.exe --sample F50 artifacts\F50.json   # also F G
.\target\release\eight-schools-regression.exe
$env:PYTHONUTF8 = 1; python analyze.py
```

`src/main.rs` and `analyze.py` are WP2's runner and analysis with only the arm
list changed; `src/eight_schools.rs` is WP3's runner with `SEEDS = [82001]`.
The `.venv-ref314` interpreter from WP2 (arviz 1.3) was used for analysis.
