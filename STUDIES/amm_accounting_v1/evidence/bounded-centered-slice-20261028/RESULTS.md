# Analytically centered independent control

All three caps passed every physical mu,log_sigma,beta,z diagnostic for both
the centered slice control and the frozen rescaled NUTS reference. Maximum
absolute coordinate-mean differences were 1.774/2.517/1.457 combined MCSEs for
caps .5/1/2, with none above four. These are descriptive comparisons rather than
simultaneous confidence bounds or a proof of general posterior fidelity.

The reference center was fixed from the Gaussian linear tilt at sigma=cap,
not estimated from NUTS draws. The exact Gaussian-density ratio retains every
target factor. Starts, seeds and proposal centers differ from the failed
zero-centered panel, as declared; this is not a controlled single-factor timing
benchmark. The earlier failures remain preserved without replacement.

All twelve chains completed within bounds. Campaign elapsed 6.000 seconds,
peak RSS 737,701,888 bytes, output 7,200,473 bytes; all groups drained and sources
stayed unchanged. The 7,073,008-byte archive matched its remote SHA256. Source and
comparison-input bindings, all arrays' shapes and finiteness were checked locally.
Complete small warmup/draw/work arrays are included here. FULL-MANIFEST.json is
the frozen NUTS reference inventory; ARCHIVE-MANIFEST.json is this archive's.

Together with the six qualified longer-data comparisons, this supplies bounded
synthetic two-method evidence across the declared nine cases. It does not select
a prior cap, establish WALNUTS sampling performance, or validate the market
observation model, predictions, decisions or profitability. The next work should
admit the native rescaled WALNUTS implementation, then move toward declared
market evaluation rather than expanding this synthetic exercise indefinitely.
