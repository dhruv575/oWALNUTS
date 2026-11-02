# Spatial precision followup

The additional native-grid seed passed with min bulk ESS 2304, no divergences
and no depth hits. Its physical means agree within 0.052 pooled SD with each
historical reference group, but narrowly miss the historical 0.05 SD pairwise
gate against one qualified WAL group. Do not claim reference qualification.

Run one independently seeded precision pilot, 954100004, with 4000 retained
draws and otherwise identical native-grid settings. Compare all 405 physical
means, SDs and MCSE with all four historical groups; preserve every comparison.
The historical combined reference remains unqualified regardless of this
pilot. This tests stability and supports a later separately reviewed reference
study, not heldout prediction or application value.

Reserve four CPUs; earlier extra seed is complete. Two old four-core controls
may overlap this job, or the two queued grid pilots may overlap it: max 12.
Retain 900 seconds / 2GiB limits. Raise this one job's output cap to 32MiB for
the doubled raw draws. Estimated total lane output remains below 200MiB;
verify actual byte count before launching, with 1GiB disk headroom required.
