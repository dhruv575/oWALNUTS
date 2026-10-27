# Acquisition-only admission, not scoring authorization

One local acquisition is proposed, with AWS stopped. All methods, dates and
comparators in PLAN-DRAFT.md are fixed before acquisition. Raw values remain
quarantined: only response status, expected timestamp counts, domain/schema
validation, byte counts and hashes may be inspected before full scoring freeze.
No return distribution, volatility, plot, forecast fit or outcome-selected
period/method change is allowed during that interval.
Later scoring admission requires terminal.complete=True and matching sealed
bars/protocol/source hashes, never the mere existence of bars.json (which could
precede a failed final integrity check).

Run the exact reviewed acquire.py with a new output directory and a separately
authorized immutable protocol binding its byte hash. Python3.11 executable:
`C:/dev/owalnuts/integrations/python/.venv/Scripts/python.exe`.
Proposed output: `C:/dev/owalnuts/target/fresh-real-august-acquisition-20261027`.
Refuse an existing directory. The parent owns launch and process monitoring.

The external monitor must cap total process elapsed at300seconds, sampled owned
RSS at512MiB and output at64MiB, record PID/start/end/exit/termination reason and
drain owned processes. These are acquisition-only caps; compute has its separate
unexecuted envelope. The collector enforces37requests, at least.5seconds between
request starts,2MiB per response,16MiB raw response total and no redirect/retry.
Its20-second urllib timeout is an inactivity timeout, so it does not replace the
external hard elapsed-time cap. An interrupted request/start marker and monitor
record remain evidence even if the collector cannot finish its terminal record.
The outer record must classify the most recent unmatched request index as
interrupted when the process is killed or times out; missing terminal/raw body
must never be interpreted as a successful request.

Preserve every HTTP/API/network/schema/cap failure and all returned raw bytes up
to the declared response bound. No retry, alternate host/instrument/period or
changed gap rule is authorized. A failed acquisition is reported as failed; a
separate parent-reviewed infrastructure recovery would be required to continue.

Parent separately checked the outcome-free history-host public/test endpoint and
received HTTP400 Bad request. That may reflect an unsupported test route and does
not establish chart availability. No market-data endpoint has yet been called.
The first fixed chart request itself is part of this one preserved acquisition,
not an unrecorded availability probe.
