# Centered latent-block development

The fixed market study flagged scale and terminal volatility for both specialist
variants on all 24 windows. Improving mu alone was insufficient. A new
development-only transition adds fixed 16-state physical-path blocks after the
existing interwoven sweep. No market-performance claim is made for this code.

For stationary AR(1) h with mean mu, innovation scale sigma and fixed rho,
the prior precision is Q/sigma². For n>1, Q has endpoint diagonals 1,
interior diagonals 1+rho² and adjacent off-diagonals -rho. For n=1 its single
entry is 1-rho². Conditioning a contiguous block B on its complement gives
precision Q_BB/sigma² and mean
mu + Q_BB⁻¹ rho times the adjacent outside deviations from mu, placed at the
corresponding block endpoints. The implementation caches this geometry, not
state-dependent draws or posterior results.

If Q_BB=L Lᵀ, whiten with Lᵀ(h_B-mean)/sigma and apply the existing elliptical
slice transition. Map back using sigma L⁻ᵀ. The likelihood is the exact
augmented Gaussian observation likelihood conditional on the existing lambda
and beta draws. Missing observations contribute no likelihood; their latent
states remain in the prior. Updates proceed in fixed block order. Reconstruct
the noncentered innovations after the full pass, preserving mu, sigma and beta.
No approximate log-chi-square mixture or changed posterior target is introduced.

Three tests verify prior density ratios at initial/interior/terminal/full and
single-state blocks, full augmented-target density ratios including missing
observations, and nonmutation of input/global parameters. These mathematical
checks do not establish mixing or precision. The existing ESS evaluation cap
and total density-evaluation budget still abort explicitly on exhaustion.

The four-chain literal development fit completed and drained at
`/home/ubuntu/lanes/blocked-development-20261028/run01`, using fixed 1000 warmup
and 2000 retained sweeps. Each chain has a 300-second external cap (295 seconds
internal), and the campaign has a 360-second outer cap. Four disjoint single
cores are used. The prior mathematical checks passed in the pinned AWS runtime;
sources, runtime binaries and four external seeds are bound in the preserved
plan. No chain was retried. All four chains retained 2,000 draws and all 254
coordinate diagnostic flags passed. Terminal-volatility bulk ESS was 3726.74
(the previous interwoven fixture: 1365.9); log_sigma bulk ESS was 3444.19.
Log-density MCSE at [-.005,0,.005] was [.007705,.001836,.006324], versus
[.012744,.003077,.010425] previously. Signed reference discrepancies were
[-.000781,-.001658,.003446]. Keep the fixed prior reference and both old methods
visible: this is one development fixture, not a market or speed benchmark.
The verified local archive contains full draws and analysis. Compare all chains to the already preserved reference,
followed by a separately declared all-window test only if readiness supports it.
Retain the existing original/interwoven market failures unchanged. Block size 16
is an engineering choice fixed before this variant's sampling, not an optimized
or uniquely favorable setting. Blocking and elliptical slice are established
methods; this implementation is not a claimed novel algorithm contribution.
