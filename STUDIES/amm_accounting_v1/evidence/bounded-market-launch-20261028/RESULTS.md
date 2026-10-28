# Fixed real-market study launch

The complete 72-cell/two-method schedule is frozen, with six batches of twelve
consecutive cells and a collision-free scalar seed reservation. Local reconstruction,
schedule and score-decomposition tests passed (four tests). The AWS failure-isolation
test passed: a first-method resource failure still attempted the second method and
retained both statuses. Each method has its own 400-second child-process limit.

The first launch failed before any batch directory or sampling process was created:
the runtime binary hash check passed a string to a Path-only helper. The corrected
call explicitly constructs Path(file). The original source, frozen manifest and
seed audit are preserved under prelaunch-failure, together with the one-time
amendment script and receipt. The amendment verifies that only this exact source
change occurred and that seeds/inputs stayed unchanged. No sample was replaced.

The launch archive excludes active batch outputs. Its 379,212 bytes matched the
remote SHA256, and all frozen source, seed-reservation and amendment bindings were
verified locally. Full prepared fixtures and baseline records remain included.

Batch 00 subsequently completed all twelve cells; both methods passed their physical
and predictive-functional diagnostics in all cells. It took 133.871 seconds, with
peak RSS 9,355,280,384 bytes and output 1,011,448,478 bytes. All process groups drained
and source hashes stayed unchanged. These are four development origins across
three caps, not the whole study or evidence of profitability. Full batch evidence
is being archived separately. Batch 01 was launched after disk/resource admission;
its results are not implied by this launch record.
