# Rate-exchange mechanism pilot, frozen before execution

Four overdispersed chains from the archived two modes. Primary Hessian whitening;
fixed WALNUTS step 0.05, depth 12, max energy error 1; no adaptation. Compare
plain transitions against identical transitions followed by one global and one
uniformly selected subject exchange per chain, each with exact MH correction.
60 chunks of 25 transitions; first 20 chunks discarded. Retain the final state
of each remaining chunk (40 per chain), after the MH moves where enabled.
Seeds 932100001 (plain), 932100002 (jump), with separate seeded MH stream.
Bound each job to 300 seconds, 2 GiB RAM, 16 MiB output. Record all target calls,
errors, mode occupancy, crossings, acceptances and elapsed time. This is a
mechanism test, not a qualified posterior reference or NUTS comparison. Success
requires all secondary-started chains to escape; it does not establish correct
mode probabilities, efficiency, or novelty. Preserve failures.
