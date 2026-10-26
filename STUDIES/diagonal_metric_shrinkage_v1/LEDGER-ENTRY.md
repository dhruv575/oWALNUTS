### WP81-DIAGONAL-METRIC-SHRINKAGE-V1: Stan's 1e-3 metric anchor over-states the variance only on sblrc (5 coordinates, 12x) and diamonds (1 coordinate, 4x); nutpie's own metric sits below the variance yet steps 1.3-19x larger; neither research regularisation meets the rule (1.025x, 1.017x); keep Stan

- **When and where.** 2026-10-26 on `wt/metric-shrinkage`, preregistered at
  `65208fb7`. Library `f52537a1` adds the research-only
  `StanLowAnchor` and `StanCoordinateCap`; the default stays bit-identical.
  - 204 cells (house 17 x seeds 810101-3 x {default, lowanchor, coordcap,
    nutpie}) and 30 funnel runs, on lane 1 (pinned, co-tenanted), no reruns.
  - A-1: analysis caching only.
- **Descriptive.** oWALNUTS's installed metric over its own-draw variance:
  - 0.9-1.1x everywhere except sblrc (5 coordinates at up to 12.2x),
    diamonds (1 at 4.3x) and an hmm_drive_0 stuck-chain artefact;
  - nutpie installs 0.01-1.0x (accel_gp: all 66 coordinates below 0.39x).
  - D1 and D1b failed.
- **Rule.** Both candidates pass R1, R5, R6 and R7, and fail R2 (1.025,
  1.017), R3 (1.000) and R4 (0.994, 0.982). Each is identical to the default
  on 27 of 51 cells; sblrc rises 1.67x / 1.79x and earnings falls 0.73x /
  0.88x.
- **Next decision.** Keep Stan; no flip. The step gap on the other 15
  models is not the regularisation. Next candidates are step adaptation
  (the dual-averaging target statistic) and the metric's overall scale.
