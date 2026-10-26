# WP65 part (b): fault rate per dispatch path

sblrc-blr, 4 chains / 4 threads, 1,000/1,000, seeds 65201001..65201500 shared by the paths; one child at a time, pinned to cores 4-7.

| path | execution | children | faults | 95% upper bound | fault kinds | median sampling wall s |
|---|---|---:|---:|---:|---|---:|
| serialised | DirectSerialised | 500 | 0 | 0.5974% | — | 0.354 |
| replicated | ReplicatedConcurrent | 500 | 0 | 0.5974% | — | 0.088 |
| threaded_direct | DirectConcurrent | 500 | 0 | 0.5974% | — | 0.105 |

Parity serialised vs replicated: 500/500 identical fingerprints and call counts; serialised vs threaded_direct (different library build, reported): 500/500.
Interrupted launches: none.

| prediction | held |
|---|---|
| B1_zero_faults_every_path | True |
| B2_serialised_replicated_fingerprint_parity_every_seed | True |
| reported_serialised_vs_threaded_direct_parity | reported |
