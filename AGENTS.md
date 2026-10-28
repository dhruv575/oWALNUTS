# AMM research operations

Dhruv's standing preference (2026-10-27): keep the existing AWS research instance
productive across experiments. Do not stop it merely because a study has finished
or its evidence has been archived. Maintain a useful research queue and continue
with the next reviewed experiment.

Monitor utilization, job progress, memory and disk space. Keep individual jobs
bounded and preserve their evidence. Investigate stalled jobs and lost watchers
instead of leaving the machine idle. If no useful work can proceed, use judgment
about stopping the instance and explain the reason.

The research objective is a practical, statistically proper AMM research system.
Predictive accuracy, posterior fidelity, decision value and profitability are
separate claims. Deployment is not the present objective.

Dhruv authorizes periodic pushes of reviewed, tested research checkpoints to the
existing Git remote while experiments continue. Do not hold completed checkpoints
for unrelated future studies. This authorization covers Git updates, not package
publication, application deployment, or trading. Preserve unrelated local edits.
