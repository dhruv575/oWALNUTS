# Timing scope limitation, identified during chunk4

The frozen protocol asks for all fitting time. Inspection of hybrid_prepare.py
shows that its reported component timers begin after parsing input and creating
the BridgeStan model. They cover score evaluations, gate computation, Fisher
fitting and curvature/block fitting, but omit worker startup, model loading,
JSON IO and orchestration. Per-job supervision elapsed time retains these costs,
but fit work is shared among experimental arms, so those elapsed times cannot
be assigned fairly to separate production paths after the fact.

Record this as incomplete end-to-end timing accounting, not a speedup result.
Do not compare the recorded component times as full wall-clock cost. The primary
prespecified continuation gate is ESS per total target/gradient calls, and every
pilot, stage,400 score calls and64d probes is charged as required; its accounting
is unaffected. No runtime superiority claim follows, especially against an
optimized Fisher implementation. Future timing validation must execute each
policy's complete setup separately and time from invocation through completion.
No sampler, gate, seed, diagnostic threshold or existing evidence is changed.
