# First shifted-window warm-versus-cold panel

All four fixed pairs completed, with every coordinate passing Rhat<=1.01 and
bulk/tail ESS>=400 for both methods. Retained divergences and depth-limit hits
were zero. Maximum absolute mean differences in combined-MCSE units were
1.874,2.193,3.084,3.043; no coordinate exceeded four. This is one synthetic
shift per fixture with an explicit common initial price of zero, not a
historical rolling forecast or calibration result.

Warm sampling seconds were .634,1.047,40.168,79.399. Cold route seconds were
14.529,14.611,30.182,26.475. Warm timing excludes native compilation and input
loading; cold timing includes Stan compilation, adaptation, sampling and trace
serialization. Neither includes all campaign overhead. These are not matched
precision or end-to-end latency comparisons. In particular, the long warm
routes are slower even with this favorable accounting, so this study does not
establish a useful speed advantage. A smaller refresh budget must demonstrate
accuracy rather than merely reduce wall time.

Outer campaign elapsed 119.043 seconds, peak RSS 4,761,927,680 bytes, output
338,792,732 bytes. All owned processes drained; sources stayed unchanged.
The complete 333,463,421-byte downloaded archive matched the remote SHA256;
all launch source bindings were verified. Full draws and diagnostics remain
in the archive, with hashes in FULL-MANIFEST.json. The subsequent predictive
analysis reloaded all eight traces and reproduced every coordinate summary;
see ../price-cell-predictive-20261028/RESULTS.md. The exact-version S3 restore
also matched the full archive (S3-VERIFIED.json).

Next analyze bounded predictive CDF functionals from these same draws, checking
quadrature convergence against numerical integration. Latent-increment CDFs
are not observed-price-cell forecasts, empirical predictive accuracy, economic
utility, or profitability. Preserve these distinctions in subsequent designs.
