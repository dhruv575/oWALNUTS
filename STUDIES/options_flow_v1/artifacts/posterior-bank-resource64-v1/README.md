# 64-fit-shaped computational resource probe

This is a computation test using deterministic copies/transforms of **two** saved reference pilot fits. It is not64independent posterior fits, a reference bank, or an accuracy/coverage result. Statistical outputs were deliberately discarded.

The frozen workload used64fit-shaped inputs, four chains, paired4000/8000 prefixes, five parameters/two endpoints, observed predictive cached-CDF endpoints, and30000shared bootstrap multiplicities. Forty parameter batch calls covered pooled high/low and both backend high-length groups. Parameter offsets were exactly `(copy_index - 31.5) * 1e-6`. Cached predictive data came from the earlier saved-pilot grid; no new posterior sampling or CDF integration occurred.

The original worker completed with exit0 on CPU0 under the900second/8GiB containment limits. Outer elapsed255.7417s; analysis255.0103s, comprising174.3810s in40parameter callbacks and80.6293s in remaining analysis. All30000joint bootstrap rows were produced. Peak committed memory1,543,786,496bytes. The workload met its resource cap; diversity/cache behavior of64fresh fits may differ.

`config.json` binds exact source/input hashes. `executed-sources.zip` preserves executed source bytes; `evidence.zip` preserves original compact records. `root-audit.json` contains the independent18-check review; `resource-audit.json` is the worker-owner check. Run `python replay_audit.py` to recheck archived hashes, counts and containment without sampling. Original compact-array hashes remain bound in the config; copied pilot data are never eligible for the future reference bank.

No quantile-kernel optimization or statistical threshold was changed following this probe. A future bank still requires fresh audited streams, fixed expected-fit denominator, independently reviewed source/runtime bindings, all diagnostic/numerical gates and explicit achieved uncertainty.
