# Posthoc workflow cost diagnosis

This investigation uses saved outputs from the frozen 72-fit comparison. It does not alter its failed 1.25 lower-bound runtime gate, and it contains no new sampling. All measured prototypes and reports are separate from the original artifacts.

## What the saved phases show

| Phase | Public total seconds | Reference total seconds |
|---|---:|---:|
| adapt | 966.39 | 1049.36 |
| batch | 908.51 | 1418.60 |
| evaluation | 246.22 | 287.85 |
| serialization | 251.87 | 251.85 |
| compile | 100.77 | 0.00 |
| parity | 49.09 | 52.21 |

Reference compilation is included in adaptation/batch phases; the zero standalone compilation entry is not zero compilation cost. Phase timers measure broad workflow regions, not isolated CPU profiles. Public compilation is 3.7% of full cost; public adaptation and retained sampling are 69.2%. Evaluation and serialization are about 9.1% and 9.3%. Controller postprocessing is 37.25 seconds public and 35.22 reference over36 workflows each; it must remain symmetrically costed.

Public stops: one at1000,26 at2000,9 at4000. Reference stops:28 at2000,8 at4000. Both write80 cumulative raw artifacts:17.204 GB public and16.859 GB reference. These counts include each attempted prefix, not only the final draws.

## Lossless storage prototype

CPU0, both saved pair00 final arrays of shape4?2000?1012, three repeats per format with alternating order. Exact float64 bit patterns and all original non-array metadata agree in every round. The binary format uses allow_pickle=False .npy plus JSON metadata binding dtype, shape and array SHA256; full-array rereads and SHA checks are included. OS caches are uncontrolled and writes do not fsync, so this is exploratory local workflow IO, not durable-disk throughput or a sampler speed benchmark.

| Arm/format | Write median s | Read median s | SHA median s | Size MB |
|---|---:|---:|---:|---:|
| public/json | 3.822 | 2.356 | 0.143 | 242.26 |
| public/npy | 0.142 | 0.073 | 0.040 | 66.61 |
| reference/json | 4.057 | 2.368 | 0.144 | 240.81 |
| reference/npy | 0.225 | 0.067 | 0.038 | 65.01 |

Even eliminating ALL measured serialization from BOTH workflows would move their point cost ratio only to 1.2074; this optimistic arithmetic counterfactual cannot establish the1.25 lower-bound gate. Binary storage is nevertheless worthwhile for usability, disk footprint, memory pressure and replay cost. It preserves gates and posterior values, unlike dropping diagnostic checks.

## Prioritized next changes

1. Add one shared lossless array-artifact contract for both workers and all readers. Keep immutable manifests, original metadata, all attempted prefixes and exact corruption/shape/dtype validation. Initially retain separate prefix arrays; a later chunk store can avoid rewriting identical earlier draws only if every tier manifest explicitly binds ordered chunks and replays identical arrays. Existing historical JSON artifacts remain untouched.
2. Reuse canonical conversion for already converted chunks. Both workers currently concatenate and reconvert their complete retained history at each tier. The transform is independent per posterior draw, so cache canonical chunks and reconstruct exact ordered prefixes. Require bitwise whole-prefix versus chunk-conversion tests over real saved samples; keep every tier diagnostic evaluation. The current timings do not isolate this conversion, so no measured saving is claimed.
3. Optimize diagnostics only through exact equivalent computation: canonical coordinate rank/Rhat/bulk/tail calculations are repeated1012times, and several physical functionals duplicate direct coordinates. Cache strictly identical coordinate arrays/results within each tier, or batch existing ArviZ primitives with full scalar parity, including threshold-near cases. Never carry diagnostics between prefixes or remove latent-coordinate checks. Parent is inspecting this path separately.
4. Profile the actual public compiled target and Rust trajectory execution at saved representative positions. Public retained sampling makes10,937,995 target calls; phase-average cost is83.27 microseconds/call, including integrator/control overhead, not isolated density cost. Only33,212 retained reverse calls (0.30%) occur, so eliminating reverse accounting cannot explain a large win. Public warmup costs966seconds across11,922,408calls; target and vector arithmetic are a more consequential place to investigate. Reference17,730,272 leapfrogs average80.01microseconds per step including other work; these are different units and must not be called identical target-evaluation timings.
5. Keep persistent-service cost a separate estimand. Public immutable PyMC target compilation can be reused for repeated fits to the exact same posterior with fresh adaptation and RNG. Changed data must create a fresh frozen target unless an independently tested dynamic-data interface exists. NumPyro can amortize compilation with runtime same-shape arguments too. Compare fresh and persistent workflows symmetrically, record first/later fits, and preserve fresh adaptation for each posterior. Earlier A/B/A development evidence does not turn the present cold comparison into a universal throughput claim.

## Validation and limits

Scripts: inspect_reports.py, array_probe.py. Evidence: phase-summary.json binds all72 reports and events; work-summary.json records saved counters; array-probe/result.json binds source and input hashes; probe-summary.json contains medians. All12 IO round trips passed bitwise and metadata equality. No source or sampler behavior was changed, no actual candidate trajectories were generated, and no diagnostic gates were relaxed. Resource timings are posthoc and cannot replace a prospective matched workflow comparison.
