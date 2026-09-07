# Open questions (as of 2026-09-05)

Ordered by expected value. Each names the evidence that opened it.

1. **A dual-averaging statistic that separates one failed refined leaf from a
   too-large step.** WP40 showed the healthy-model gap is warmup: single-leaf
   reverse-coarser rejections cut the step 3 to 10x on every model at the same
   rate, and every fix that saved warmup gradients ended at a larger step and
   lost on the GP and eight-schools targets. Pairing the skip statistic with
   acceptance targets of 0.85 and 0.9 (WP40 addendum, 2026-09-06) also loses,
   so a smaller step of the same kind is not what the targets want; the
   statistic itself has to change. Any adoption needs a preregistered decision study on fresh seeds with the
   four targets as the deciding class.
2. **`diamonds` at the depth-10 cap** (WP31, WP32): 246 to 539 capped draws
   per seed at step 0.003 to 0.005 in every arm; not a metric floor case.
3. **The funnel's per-chain step collapse at the defaults** (WP28, WP32): one
   chain per seed at h near 0.01 with omega R-hat 1.01 to 1.04. Unbiased, not
   efficient. `levels8 + delta 0.5` is the known efficient setting and is not
   yet measured on posteriordb.
4. **Target-adaptive delta** (WP34, WP37A): fixed delta 2 is not qualified;
   a rule that adapts delta from the observed leaf-error distribution is
   unmeasured.
5. **Global to path scale coupling on state-space targets** (WP4b, WP17,
   WP21): the arrowhead line is the best per-call mechanism in pilots and
   needs a six-global generalisation, Python exposure and a preregistered
   confirmation. sspd-10 remains unsolved by every Euclidean configuration.
6. **Start rules**: `hmm_drive_0`'s second-mode draw and `lotka_volterra`'s
   `rk45`-boundary starts decide gates by lottery (WP25, WP29, WP31). A
   cross-chain mode check at the end of warmup (the `ChainDisagreement`
   diagnostic) is the instrument; an init-time ODE check was never tried.
7. **Rescue as an observe-only warning** (WP36): automatic cross-chain action
   is out of the defaults; a warning or a narrowly scoped step-only policy is
   the allowed next design.
8. **Windows native root cause** (WP35A, `bridgestan_lifetime_v1`,
   `bridgestan_owned_worker_v1`): mitigated at 3 to 5x sampling cost on
   Windows GNU; MSVC and multi-worker Windows unqualified; root cause not
   established.
9. **Reverse-coarsening cost on `accel_gp`** (WP34, WP39, WP39B): 54 %
   reverse-coarser stops and 0.47x CmdStan; not a truncation artefact. Its
   difficulty is unexplained.
10. **Paper-mode borderline omega R-hat at 4 x 50,000** (WP14, WP12): third
    sighting; a longer run or pooled delta would settle whether it is run
    length.

Closed lines, so they are not reopened: reverse-coarsening as truncation
(WP34 to WP39B); coarsest-first reverse order (WP37B); Appendix C as the
default (WP22, WP23); full scale non-centering (WP17); chain rescue as a
default (WP36); warmup-schedule levers for the healthy-model gap (WP40).
