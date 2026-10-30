# Off-device archive and verified reclamation

Training archive172members,503095310bytes,SHA256
da938d25f945fa8affb85753450c7cf6d80a6a831257cc5eab893158d3d69498,
private S3 version awDQS7v.mEXHblmQ_VW1wQPdOACoiPjf.

Application archive433members,405060066bytes,SHA256
b33d881c03b5fd5e98c94bdee44b4ebb9372ff26bcdcd37f91f4f64776a6de05,
private S3 version Jm4xpRyfvJce_ocnfzMa15Aj7LA18cBX. It depends on the exact
training archive above for reference draws and original runtime dependencies.
Both archives were member-hash verified locally and downloaded by exact S3
version to verify complete restored SHA256. Receipts live under research-ops/
archive/real-counts-{training,application}-s3-20261030.

After completed prediction and independent audits,23 raw files totaling
568628842bytes were reclaimed from the completed AWS reference,importance-screen
and sampler-screen directories. Each file matched an archived member by size
and SHA256 on both local and remote checks. A fresh remote audit verified no
dependency readers before individual unlink operations; no recursive deletion.
Sources,summaries,runtime libraries and fresh/predictive evidence remain on AWS.
Local raw copies also remain. Reproduction of the retired studies must restore
their raw files from the verified archive; do not treat their old AWS directories
as complete raw evidence. Full paths and hashes are retained in
research-ops/archive/real-counts-reclaim-plan-20261030.json and its audit/deletion
receipts. Free root disk rose from about1.1GiB to1.7GiB.
