# Reverse-schedule allocation mechanism screen

Release baseline da42c8fb built on EC2; five independent baseline processes
completed, followed by eight alternated-order baseline/candidate pairs. Each
process evaluated all three existing exposed workloads, with --repeat 1.
All process exits are zero. Calls and retained-draw fingerprints match for
every paired workload. Fingerprints are limited evidence, not full oracle
parity or posterior validation. No production code changed.

Median baseline/candidate wall ratios: funnel 1.053 (range 1.014--1.080),
Gaussian 0.971 (0.963--0.990), Eight Schools 0.990 (0.981--1.034). The candidate
reduces funnel allocations/call from 0.24 to 0.19 (rounded), with the other
two unchanged at 0.57 and 1.27. These sub-100ms timings are a mechanism screen,
not a confirmatory performance claim. The unused schedule does not explain
most kernel overhead, and this candidate is not adopted. No held-out or oracle
tests were run because the performance screen does not justify promotion.

Candidate construction and bounded paired runner are preserved in candidate.py;
its hash and binary hashes are in paired01/MANIFEST.json. Compiler, build logs
and baseline source archive hash are preserved alongside the results. The
source archive is reproducible with git archive at the baseline commit.

Operations: local compilation failed because MSVC link.exe was absent. Remote
compilation succeeded in the memory-backed /dev/shm directory, avoiding disk
pressure. An initial shell loop incorrectly expanded its output filename and
overwrote its own log; the remaining run-.log is preserved but excluded. The
Python runner then collected the complete five-process baseline and separately
the complete 16-process paired experiment. No excluded measurement selects
the candidate. Temporary build artifacts remain on EC2; machine stays running.

Next: inspect larger allocation sources and the cost of high-dimensional
metrics before selecting a substantive mechanism. Prior studies already rule
out untruncated reverse orbits as a general ESS-per-gradient improvement.
Goal remains active; no practical success is established.
