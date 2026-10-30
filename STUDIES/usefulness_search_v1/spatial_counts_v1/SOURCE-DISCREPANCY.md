# Documentation and pinned data disagree on point count

The pinned bei.Rd documentation says3605 trees. Inspection of bei.rda using
rdata1.1.0 shows the stored ppp object's n field is3604. Do not append a point,
drop another point,or silently label the actual data3605. Preparation must verify
both coordinate arrays have3604 finite in-window entries and agree with stored n.
Retain original binary/documentation and record this discrepancy in the manifest.
The reason for the discrepancy is not established. Grid,split seed,exposure,
models and planned competitors remain unchanged.
