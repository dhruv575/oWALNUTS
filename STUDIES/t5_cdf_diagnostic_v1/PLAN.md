# Student-t5 CDF arithmetic diagnostic: fixed plan

This is a local arithmetic diagnostic only. No sampler calls, posterior changes,
quadrature-order changes, chain selection, qualification or default changes.
Freeze this plan before implementation/results. Owner: research/warm-precision.

For v=x/sqrt(5), integrate the exact density to obtain
F(x)=1/2+atan(v)/pi+v(5+3v^2)/(3*pi*(1+v^2)^2).
Evaluate the smaller tail using symmetry. Avoid polynomial overflow using reciprocal
coordinates. For t=sqrt(5)/abs(x)<=1/4, use the fixed convergent expansion
Q(x)=8/(3*pi)*sum[n=0..23] (-1)^n*(n+1)*(n+2)/2*t^(5+2*n)/(5+2*n).
The alternating remainder is bounded by the first omitted term; absolute target
is 5e-15 and relative smaller-tail target 5e-12 where the true tail >=1e-300.
No clipping of materially negative or above-one values. IEEE infinities map to
0/1, NaN stays NaN, signed zero maps to 1/2. Positive CDF may round to 1 when its
small complementary tail is below representable spacing; expose an SF as well.

Fixed validation grid: 200001 linear points over [-100,100], signed logspace
1e-15..1e60 (20001 magnitudes), signed logspace 1e60..1e308 (2001 magnitudes),
zero, signed infinity, NaN, smallest positive subnormal and largest float.
Add nextafter neighbors of branch boundaries abs(x)=sqrt(5),4*sqrt(5).
Compare both CDF and SF against scipy.special.stdtr, record max absolute and
relative smaller-tail error, monotonicity, bounds and symmetry. Underflowing tails
are explicitly counted, not claimed relatively accurate.

Independent checks: scipy.integrate.quad on density at fixed x=[-100,-20,-8,
-4,-1,-.1,0,.1,1,4,8,20,100]; integrate in reciprocal coordinates for positive
smaller tails to avoid infinite integration failure. Known F(0)=1/2 and
F(sqrt(5))=3/4+2/(3*pi); independent high-precision mpmath integration at
magnitudes [.1,1,sqrt(5),4*sqrt(5),20,100,1e4,1e20,1e50].

Only after validation passes, compare existing processor with scipy.stdtr versus
this exact t5 implementation on all four saved host compact draws, retaining
joint draws, GH64/128, weights, brackets, tolerances, outputs and failures.
Run arithmetic locally, no remote work. Preserve baseline and candidate outputs,
source/input hashes, runtime versions, repetitions and timing scope; JIT compilation
separate. Timing is local and cannot establish host end-to-end latency. A failed
validation blocks replacement comparison; retain negative evidence and do not
change grid/thresholds in response to outcomes without a separately recorded plan.
