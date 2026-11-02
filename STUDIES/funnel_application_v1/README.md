# Learned-scale hierarchical binomial pilot, 2026-11-01

oWALNUTS has a plausible application in estimating uncertainty across groups
when the amount of pooling must itself be learned. This synthetic pilot shows
a reliability/tuning benefit, not a unique application or a 10x speedup.

Earlier A/B screening used fixed prior scales. Here 12 group logits share an
unknown population mean and half-normal population standard deviation. One
dataset has five observations per group; the other ranges from five to 10,000.
Both were generated with small between-group variation. These are deliberately
difficult synthetic datasets, not observed business outcomes. See PROTOCOL.md.

## Main confirmation

An independent quadrature reference passed resolution, expanded-domain and
analytic-prior checks. We tested centered, noncentered and hybrid coordinates;
the confirmation uses noncentered coordinates. NUTS acceptance .99 was selected
on a separate calibration seed for each dataset; WAL acceptance remained .9.
Eight fresh seeds per dataset, four chains, 1,000 warmup and three separate
retained-draw budgets were evaluated. Gates include reference accuracy, MCSE,
Rhat, ESS, zero divergences and zero depth hits. All failures are preserved.

| Dataset / engine | Pass at 1,000 | Pass at 2,000 | Pass at 4,000 | Median sampling seconds at 4,000 |
|---|---:|---:|---:|---:|
| Weak / NUTS .99 | 2/8 | 8/8 | 8/8 | .349 |
| Weak / WAL .9 | 7/8 | 8/8 | 8/8 | .264 |
| Mixed / NUTS .99 | 0/8 | 3/8 | 2/8 | .464 |
| Mixed / WAL .9 | 0/8 | 1/8 | 8/8 | .499 |
| Mixed / NUTS .999, post-hoc control | — | — | 8/8 | .667 |

The last row reuses the eight mixed-case seeds and is a separately labeled
conservative control, not independent replication. It closes the reliability
gap. Its sampling time is about 1.34 times WAL's; serial versus concurrent
execution and small absolute runtimes limit the timing comparison. Cold worker
medians were 2.786 seconds for this NUTS control and 2.830 for WAL, so there is
**no demonstrated end-to-end speed advantage** on this small problem.

The budget ladder also does not establish a universal cost win. In the mixed
case, NUTS .99 reaches a first passing budget on four of eight seeds, while WAL
does on eight of eight. Censored NUTS runs must not be counted as fast successes.
Passing at a smaller budget is not proof that a later independent run will pass.
Eight seeds characterize this pilot only, not a population reliability rate.

## Why the uncertainty matters

The numerical reference gives P(tau < .1) of .1250 for weak data and .7703 for
mixed data. This quantity describes uncertainty about whether group variation
is small. A joint noncentered Gaussian Laplace approximation gave zero for both
and badly missed other posterior moments despite a valid local mode/Hessian.
That is a failure of this particular approximation, not all Laplace methods.
Carefully tuned NUTS and WAL agree with the reference.

This mechanism is relevant to conversion/failure rates across small groups and
other hierarchical estimates. It does not measure treatment effects, decision
value, profitability or predictive improvement. The independent integration
itself took roughly 1.3–1.4 seconds after imports for all reference checks, making
it a strong cheap alternative for this small conditionally independent model.
We have not shown that this application needs WAL specifically.

## Evidence and limitations

- primary01: original calibration and two-seed validation; no fully qualifying
  original NUTS calibration, so its 1/4 versus WAL 4/4 is not a fair speed claim.
- followup01: stronger acceptance and hybrid controls with two fresh seeds.
- matched01: nutpie 0.16.11, separate calibration plus 96 confirmation fits.
- conservative01: eight post-hoc NUTS .999 mixed-case fits, all passing.
- Each archive has a SHA256 manifest and local VERIFIED.json. Compressed raw
  draws and native binaries are retained locally but excluded from Git. RAM
  staging on EC2 was streamed and verified before being called archived.
- RAW-AUDIT.json checks physical-coordinate functional means directly from raw
  draws for the original 154 fits. Source/ABI/gradient checks and an analytic
  reference-prior audit are also preserved. Gates were not relaxed.
- The installed WAL 0.3.0 extension was used, not a rebuild of the latest Git
  optimizations. Original paired runtime used nutpie 0.16.8; confirmation used
  0.16.11. RUNTIME.json records binaries and versions.
- Timings include warmup in the sampling kernel; imports/diagnostics are reported
  separately as worker time. Calibration cost is retained, not amortized away.

Reproduction: prepare.py freezes the datasets; compile model.cpp with
`g++ -O3 -std=c++17 -fPIC -shared model.cpp -o model.so`, run preflight.py,
reference.py/audit_reference.py and campaign.py in the recorded runtime.
Modern confirmation uses backend_modern.py deployed as backend.py and
matched_campaign.py. These research launchers contain recorded EC2 lane paths;
adjust those explicitly on another host. The exact deployed files are archived.

Next research question: does the benefit survive real data and coupled
hierarchical effects where simple conditional marginalization is less effective?
Require tuned/reparameterized NUTS and a strong approximate or marginalized
baseline. No uniqueness claim until that comparison succeeds.

## Fresh serial confirmation update

The subsequent 96-fit serial01 campaign used new seeds and froze NUTS .99 for
weak data and .999 for mixed data. At 4000 draws, weak-data runs passed 8/8 for
both engines. Mixed-data runs passed 7/8 for NUTS and 6/8 for installed WAL.
Median sampling times were .737 and .517 seconds respectively. Thus the earlier
8/8 reliability result did not reproduce perfectly; a sampling-time advantage
alone does not establish an advantage at matched accuracy. All 589 archived
files were SHA256-verified locally. See SERIAL-CONFIRMATION.md for the protocol.

LATEST-BUILD-PROTOCOL.md specifies a separate comparison of installed WAL,
rebuilt committed WAL and conservative NUTS with larger budgets and increasing
likelihood concentration. Its results must not be conflated with serial01.

That comparison is now complete: see [LATEST-BUILD-RESULTS.md](LATEST-BUILD-RESULTS.md).
The rebuild gave only a median1.8% sampling speedup over the installed binary.
A hybrid rewrite gave both samplers reliable concentrated-case results, with
WAL about1.4x faster at10x concentration but NUTS about1.8x faster at100x.
There is no demonstrated broad or order-of-magnitude advantage.
