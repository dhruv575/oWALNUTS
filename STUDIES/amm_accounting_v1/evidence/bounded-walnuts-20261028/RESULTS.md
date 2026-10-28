# First fixed bounded-target WALNUTS panel: incomplete

Four of nine fits completed: all three T=12 all-zero cases and the cap-.5
T=250 distinct case. Every completed fit passed all physical and b diagnostics,
with zero retained divergences or depth hits. No full reference-mean comparison
has yet been performed for those four fits.

Five T=250 cases aborted with a fatal NaN target callback at transition 1: all
three two-zero cases and the cap 1/cap 2 distinct cases. They remain failed slots;
no replacement seeds or smaller step sizes were substituted. The outer campaign
exited 1, all process groups drained, and sources stayed unchanged. Elapsed 9.976
seconds, peak RSS 1,633,886,208 bytes and output 43,534,329 bytes.

The complete 38,047,972-byte archive matched the remote SHA256 after download.
The verifier checked source bindings, all nine terminal outcomes, four retained
array shapes/finiteness and full warmup/retained diagnostic-event array shapes.
The raw archive is target/bounded-walnuts-full.tar.gz; no S3 restore claim yet.

A separate single-thread diagnostic replay of fit 1 reproduced the chain 3,
transition 1 failure and captured a finite proposal with mu=-687052.926,
eta=29849.650 and log beta scale=-343526.463. The intermediate scale underflows
to zero in double precision. The callback explicitly rejects this conversion
with NaN. This does not establish that the mathematical target has zero density
there. In particular, treating beta as exactly zero would mis-evaluate tied
observations because the standardized residual can remain finite.

Next derive the likelihood and gradient directly in scaled/log coordinates,
verify against arbitrary-precision calculations at the captured state and other
tail cases, and repeat deterministic parity before any separately declared
sampling follow-up. Do not merely convert all NaNs into rejections.
