# Associative mixed-reference admission review

The current adapter branch admits the actual associative mixed worker schema:
report.json, explicit implementation/coordinates/settings, all attempted tier
reports and raw paths, actual full diagnostic family, first-pass stopping and
matched physical starts. The subsequently added checkpoint iteration/prefix
checks and derived mixed sampling-start checks resolve the main static gaps.

Two independent saved-output compatibility tests passed. Evidence is in
saved-reference-test-v1/test-result.json and saved-reference-test-v2/test-result.json;
the latter tests the hardened adapter. The reproducible driver is
saved_reference_adapter_test.py. Each result pins the exact adapter source hash.

These are strictly schema/admission tests, not calibration evidence. They use
the historical pair00-reference output, which has a prior-generated truth
vector but was repeatedly used as one fixed posterior in earlier development.
No inference was launched. Actual fit diagnostics, intervals, truth, outcomes,
checkpoints and raw values are unchanged. Only final report source-binding
paths are remapped to byte-identical archived worker sources. A manufactured
test-only envelope explicitly carries calibration_evidence=false. Hardlinked
raw inputs must never be modified. Neither normalized test record may enter
the forthcoming fresh-dataset denominator.

The screen controller's flow-only T1000/G4 branch correctly uses explicit
dataset/init/sampler/prediction streams, shares starts with each selected
reference, gives references separate sampling/prediction streams, preserves
the40 intended outcomes and routes to associative mixed NumPyro at.9. Its
old defaults remain separate. Freeze must still inspect the actual generated
fixture/manifest/command/source bindings and exact reference index schedule.

Outstanding resource-scope correction reported to the controller owner:
execute() admission timing currently ends before report() normalization,
coverage and additional hashing. Persist those later costs separately and
clearly distinguish admission budget from total recorded experiment cost, or
include them in the prospective budget. Do not claim full workflow cost is
bounded by execute elapsed. Unstarted queue outcomes remain in descriptive
denominators but cannot be treated as iid computational failures for exact
confirmatory binomial inference.
