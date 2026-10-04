# Historical-host panel attempt: incomplete

Historical discovery succeeded and selected four contracts using only the
prespecified first day. The collector stopped on its first instrument sequence
page because response order was not monotone despite requesting ascending order.
All 344 sequence numbers in that page are unique and cover the requested
320 through 663 inclusive; some arrive out of sequence order. This supports a
collector ordering correction, not discarding or accepting a truncated panel.

The attempt used 40 requests and 5,550,541 raw-response bytes. No model was fit.
The exact 80 HTTP request/response records are losslessly archived and verified
against per-file hashes. Selection, metadata, protocol and failure status remain
separate readable files. A corrected collector must use a new attempt, preserve
duplicate/range/gap checks, and verify timestamp ties at both sequence boundaries.
