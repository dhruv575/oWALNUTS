# Frozen hybrid validation progress

Chunk1 (seeds929300001--4) completed168 bounded jobs and120 matched sampler
stages. All source, schedule, costs, branch-equivalence and durable hashes verify.
Hybrid passes4/4 on ARMA,arK,sblrc,GARCH,GP; all arms fail0/4 on centered eight
schools. Unconditional Fisher and dense each pass3/4 on GP; auto/v4/hybrid4/4.
These are interim counts, not the full study's continuation-gate result.

721-member archive restored from exact private S3 version and verified. Only then
168 redundant compressed RESULT files (62,900,362 bytes) reclaimed; originals,
private archive and historical manifests retained.

Chunk2 (seeds929300005--8) also completed168 jobs/120 stages; all audits and the
721-member exact-version private archive restore pass. Hybrid again passes4/4
on five targets and0/4 centered eight schools. Reclaimed168 redundant compressed
results (62,818,448 bytes) only after archive verification.

Chunk3 (seeds929300009--12) completed168 jobs/120 stages with all audits and
721-member archive restore passing. Hybrid again passes4/4 on five targets and
0/4 centered eight schools. Reclaimed168 redundant compressed results
(62,741,606 bytes) after verification. Chunk4 is active unchanged.
Chunk4 (seeds929300013--16) is now terminal too:168 jobs/120 stages, all audits,
721-member archive restore pass;168 redundant gzip results reclaimed after
verification. Full analysis of all16 seeds FAILS the frozen continuation gate
because regression hybrid/Fisher efficiency .807 is below .90, despite ARMA and
GARCH signals and no paired accuracy loss against auto/v4. See HYBRID-REPORT.md
and HYBRID-COMPARISON.json. No threshold or policy changes made during validation.
