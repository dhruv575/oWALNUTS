# Mixed T1000 target-only diagnosis

Both contained processes exited0; no MCMC or new random streams were used. Total outer cost11.796seconds. Five deterministic archived points include two initial states and three retained posterior states.

Public PyMC/Numba mixed-slopes block32 normalized target median: 80.498 microseconds/call over5blocks?1500calls. ctypes no-op control: 0.394 microseconds; zero-gradient1012-element control: 0.482 microseconds. Pointer creation is outside timed loops. Compilation/model construction:3.091seconds; imports remain in totalprocesscost. Existing disk compiler caches were retained. CPU0 and8GiB cap applied before numerical imports; timeout600seconds per process.

Separate JAX64 checks passed at every archived point against both direct normalized mixed density and canonical density plus Jacobian; maximum gradient discrepancy1.565e-12. This validation process did not contaminate measured target blocks. The optimized graph has91nodes, including2Scan nodes with only1/2innernodes,2CumOp nodes,8FusedElemwise nodes, and substantial slicing/allocation graph structure. Node counts do not establish individual operation costs.

The earlier complete public retained-phase average was83.27microseconds per target call. The present80.50microsecond target-only result suggests the compiled target dominates that cost. These are different runs/positions and hardware-cache conditions: subtracting them is not a precise measurement of Rust trajectory overhead. ctypes controls show Python-to-C dispatch is small here; no NumPyro leapfrog comparison is made.

Next useful optimization experiment: profile generated Numba target arithmetic/allocation and alternative mathematically identical high-level likelihood/vectorization expressions. Preserve automatic gradients, full normalization, all parameter domains, and boundary behavior; require independent parity before any workflow comparison. Do not claim tiny Scan graphs prove absence of Scan overhead without per-op evidence. This exploratory profile cannot alter the previously failed workflow speed gate.

Exact inputs/runtime/source hashes are in config.json; executed Python bytes are in executed-sources.zip with its manifest. profile-result.json stores points, gradients, first-call times and allblocks. Commands, exitstatus and hardwarecontainment are recorded perphase. No original saved artifacts or sources were edited.
