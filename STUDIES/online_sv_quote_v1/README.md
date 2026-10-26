# Online SV quote latency (WP84)

Status: preregistered at `72987d97` (before any cell), base `fa04c5b9`; executed 2026-10-26 on
the shared Linux box, lane 4 (cores 12-15), pinned, co-tenanted. 32/32 cells exited 0; none
rerun. Tables: `artifacts/results-table.md`; machine-readable `artifacts/summary.json`.

## Verdict

**The frozen "real-time" rule is not met; the README may not say "real-time".** At N = 250
the warm path is fast (median 20 ms at K = 50, 80 ms at K = 200, 100 % of ticks under 400 ms)
and stays calibrated over 100 ticks (90.1–90.3 % of its draws inside the reference 90 %
interval, early vs late within 0.003, drift bound met 6/6), but it is valid by the frozen rule
on 0–4 % of ticks, mainly because four 50–200-draw chains rarely reach R-hat <= 1.01 (K=50:
3 %, K=200: 56 % of ticks). At N = 1000 **validity could not be assessed**: the reference
(4 x 2,000/20,000) failed every tick at admission with "result data exceeds its resource
limit" (4 x 22,000 retained 1,004-D draws exceed the sampler's result ceiling), so only
latency is reported there.

| arm | N | median s | p95 s | < 0.4 s | < 2 s | valid (3 ref-MCSE) | valid (combined MCSE) | R-hat ok | drift in ref 90 % |
|---|---|---|---|---|---|---|---|---|---|
| warm K=50 | 250 | 0.020 | 0.044 | 1.00 | 1.00 | 0.00 | 0.03 | 0.03 | 0.901 |
| warm K=200 | 250 | 0.080 | 0.176 | 1.00 | 1.00 | 0.02 | 0.52 | 0.56 | 0.902 |
| oWALNUTS refit | 250 | 3.07 | 20.0 | 0.00 | 0.00 | 0.09 | 0.87 | 0.93 | |
| CmdStan refit | 250 | 6.50 | 51.5 | 0.00 | 0.00 | 0.10 | 0.82 | 0.87 | |
| nutpie refit | 250 | 1.09 | 1.54 | 0.00 | 0.99 | 0.14 | 0.96 | 1.00 | |
| warm K=50 | 1000 | 0.267 | 1.96 | 0.67 | 0.99 | n/a | n/a | n/a | n/a |
| warm K=200 | 1000 | 1.07 | 7.58 | 0.00 | 0.67 | n/a | n/a | n/a | n/a |
| oWALNUTS refit | 1000 | 16.7 | 69.8 | 0.00 | 0.00 | n/a | n/a | n/a | |
| CmdStan refit | 1000 | 42.0 | 218 | 0.00 | 0.00 | n/a | n/a | n/a | |
| nutpie refit | 1000 | 4.47 | 5.90 | 0.00 | 0.00 | n/a | n/a | n/a | |

Medians are the median of the three seed medians; p95 the worst seed. No arm had a retained
divergence on any tick. Tick-0 fit for the warm arm (not in the latency statistics): 2.2–2.4 s
at N = 250, 13.6–66.8 s at N = 1000. Coverage of the true simulated h by the 90 % interval
at N = 250: warm 0.85–0.87, refit arms 0.87–0.90. Straddle quote median absolute relative
error vs reference: warm50 1.0 %, warm200 0.4–0.5 %, refits 0.2–0.3 %.

## What the continuation API supports

`Sampler::start_session` serves one immutable target of fixed dimension: one `adapt()`, then
`draw(n)` up to a budget fixed at start. It cannot be retargeted (no new data, no dimension
change, no injected positions/step/metric). The warm arm is therefore a research-only
retarget in the study harness (`rust/src/main.rs`), built on the public `Sampler` with a fixed
diagonal metric, the carried step, `Adaptation::None` and given starts; no library change.

## Predictions

* P1 (warm latency) **partial**: N = 250 held (K=50 20 ms in 5–60; K=200 80 ms in 20–240);
  N = 1000 missed (K=50 267 ms vs 20–250; K=200 1.07 s vs 80–1,000 ms).
* P2 (oWALNUTS refit 0.3–2 s / 1–8 s) **missed** (3.1 s / 16.7 s): about 200 gradients per
  transition, not the 30–80 assumed.
* P3 CmdStan (0.4–3 / 1.5–10 s) **missed** (6.5 / 42 s); nutpie (0.3–2 / 1–8 s) **held**
  (1.09 / 4.47 s).
* P4 (primary validity <= 40 % for every arm, rule fails) **held** at N = 250 (0–14 %).
* P5 (secondary validity: refits >= 80 %, warm200 >= 60 %, warm50 >= 40 %) **partial**:
  refits held (82–96 %), warm200 52 % and warm50 3 % missed (R-hat).
* P6 (warm200 drift within bound on >= 5/6) **partial**: 3/3 at N = 250, unassessable at
  N = 1000.

## Decision rule outcome (frozen)

The warm arm must be valid and under the latency threshold on >= 95 % of ticks at both N with
drift within bound. N = 250: 0 % (K=50), 1.7 % (K=200). N = 1000: unassessable (reference
failed), which the rule counts as not met. **Real-time claim not allowed.**

## Honest README sentence

"On a 250-return stochastic-volatility model fed one return per tick, oWALNUTS warm
continuation (frozen step and metric, 50–200 transitions per chain) refreshes the posterior
in 20–80 ms median (4 pinned cores) and stayed calibrated over 100 ticks, against about 1 s
for a nutpie refit and 3–6 s for oWALNUTS and CmdStan refits; its 4 x 50–200 draws do not
reach the R-hat <= 1.01 / reference-MCSE accuracy bar, so this is a fast approximate
refresh, not a validated real-time posterior (WP84)."

## Anomalies and amendments

* A1 (post hoc, analysis only): `analyze.py` crashed on the failed N = 1000 reference; it now
  reports validity there as n/a instead of 0. No cell or rule changed.
* The N = 1000 reference failure is a result (admission-time result-size ceiling); it was
  not rerun. A reference at N = 1000 needs fewer retained draws, thinning, or a raised limit.
* Some ticks at N = 1000 took far longer than the median (refit p95 70 s, CmdStan 218 s): slow
  warmups, not divergences.
* Raw reference draws for N = 250 (`artifacts/cells/ref-N250`) are checksummed but not
  committed (size).
