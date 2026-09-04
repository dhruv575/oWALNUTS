# chain_rescue_v2 — post-run derived-analysis correction

Date: 2026-09-04
Status: **post-run; derived reporting only**

The as-executed launch, process, raw, heartbeat, stdout, stderr, cell, draw,
and original derived-analysis tree was checksummed and committed unchanged in
`b8aee0f` before this correction. No cell was launched, rerun, deleted, or
modified while preparing this correction.

This document records audit corrections to derived analysis and presentation.
It does not amend the frozen sampling protocol, change a raw observation, or
change the mechanical fallback.

## Process accounting and exclusions

- 288/288 launch markers and 288/288 process records exist.
- 281 cells are process-valid and seven are process faults.
- Six faults returned `0xC0000374`: HMM `current/92109`,
  `observe/92111`, and `two_hit/92109`; diamonds `observe/92102`,
  `two_hit/92108`, and `two_hit/92111`.
- Mesquite `current/92102` timed out after 7200 seconds after publishing a
  valid raw result; its last heartbeat was `drop/before`.
- Six triplets are invalid. Valid counts are HMM 10, kidiq 12, earnings 12,
  diamonds 9, ARMA 12, lotka 12, mesquite 11, and funnel 12.

Fault rows are now rendered as `process_fault` or `timeout` with return code,
last heartbeat, raw presence, and duration. They are not rendered as missing.

## Corrected reporting

Predictions are adjudicated independently even though the registered
completeness gate fails:

| prediction | held |
|---|---|
| P1 | false |
| P2 | false |
| P3 | false |
| P4 | false |
| P5 | false |
| P6 | true |
| P7 | false |
| P8 | true |

The corrected reports also:

- label funnel tail z as signed and show omega tail ESS;
- place the `two_hit` funnel gross red line at funnel seed 92111 in the
  registered funnel/red-line report, not in the general safety gate;
- label `0.8931682041554473` as an available-case geometric mean over 77
  efficiency ratios. The registered full efficiency gate fails because
  HMM/92104 has no ratio and the ARMA and HMM model medians are below 0.90;
- report paired posteriordb raw-to-credited pass totals of 71-to-71 for
  `observe`, 74-to-71 for `current`, and 76-to-72 for `two_hit`;
- report 117 `current` restart events, five mapped origin-overwrite events,
  and two unknown-origin events; and 58, five, and two respectively for
  `two_hit`;
- report nuisance unique-chain totals 35 versus 14, with eight wins, one
  loss, no ties, `p=0.01953125`, but only nine complete blocks;
- report efficacy as one win, zero losses, nine ties, `p=0.5`;
- report the `two_hit` funnel full gate as 4/12, with signed-tail-z failures
  at seeds 92107, 92111, and 92112;
- preserve the passing no-fire gate and the mechanical `no_rescue` decision.

## Stable-origin limitation

The frozen classifier identified stable origins only for pathological/frozen
starts in ARMA (seeds 92105, 92107, and 92112) and lotka_volterra (seed
92108). It identified zero HMM origins. This materially limits substantive
interpretation of the origin-overwrite result, but it does not alter the
registered gates or frozen fallback.
