# WP50C Phase C result: the payoff of removing serialisation

Preregistered at `ba28af73` / `3bc064c5`. One launch: 12 of 12 children ran
with 0 faults, no timeouts and no Event 1000 for the payoff exe.

**Assertions: all hold.** For every (model, seed), the following were
identical between the arms:

- the hash of the start log-density and gradient bits;
- the fingerprint of all 4×1000 retained draws;
- `target_calls`;
- `draws_observed`.

The two arms therefore produced bit-identical chains. Only throughput
differs.

## Sampling wall time and process CPU per pair

Wall times are **contended**: other agents' processes shared the machine. The
ratio is serialised over unserialised.

- **sblrc**
  - 50700701: 1.20 s vs 0.44 s, ratio **2.74**; CPU 2.33 vs 0.53 s.
  - 50700702: 1.12 s vs 0.23 s, ratio **4.92**; CPU 2.55 vs 0.67 s.
  - 50700703: 0.59 s vs 0.19 s, ratio **3.16**; CPU 1.94 vs 0.61 s.
  - Median wall ratio **3.16**.
- **arK**
  - 50700711: 86.3 s vs 7.97 s, ratio 10.8; CPU 13.2 vs 7.6 s. The
    serialised wall time is far above its CPU time, which points to
    contention.
  - 50700712: 23.0 s vs 5.69 s, ratio **4.05**; CPU 15.7 vs 8.5 s.
  - 50700713: 18.1 s vs 4.96 s, ratio **3.65**; CPU 13.1 vs 6.9 s.
  - Median wall ratio **4.05**.

The serialised owned worker also costs **more CPU**: 1.7–1.9x on arK and
3.2–4.4x on sblrc. That points to the channel handoff and lock overhead, not
merely to idle cores.

## Frozen recommendation rule: met

- Phase B `fix_supported`, under the disclosed time-window correlation.
- `static_short` 0/60.
- Phase C 0 faults, and every assertion holds.
- Median wall ratio ≥ 1.5 on both models: 3.16 and 4.05.
