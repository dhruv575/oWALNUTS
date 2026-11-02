# Fresh serial confirmation

After conservative01, freeze noncentered NUTS acceptance .99 for weak data and
.999 for mixed data, WAL acceptance .9 for both. Reuse frozen data, reference,
installed runtimes and gates. Fresh seeds 956700011..18 (weak) and
956700021..28 (mixed). Four chains, 1000 warmup, independent 1000/2000/4000
draw budgets. Run all 96 fits serially on one pinned CPU, alternating engine
order by seed. Preserve every outcome; report sampling and full worker times,
first-passing cumulative budget costs and censored runs. This addresses the
post-hoc conservative setting and timing-execution confound, not real-data
generalization. No subsequent tuning on these seeds.

Existing EC2 only, RAM staging <=128MiB, each fit <=900s and <=2GiB, root free
space floor1GiB. Stream and SHA256-verify completed evidence locally. Current
root headroom prohibits ordinary disk-staged expansions. No evidence deletion.
