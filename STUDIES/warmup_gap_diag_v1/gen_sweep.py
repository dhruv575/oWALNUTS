import os
S = os.environ.get("SWEEP_ROOT", os.path.dirname(os.path.abspath(__file__)))
M = 'C:/dev/owalnuts-wt/posteriordb-v6/STUDIES/posteriordb_bench_v6/models'
models = ('eight_schools__eight_schools_noncentered eight_schools__eight_schools_centered diamonds__diamonds '
          'earnings__logearn_interaction mesquite__logmesquite_logvash kidiq__kidscore_momhsiq sblrc__blr nes2000__nes '
          'arK__arK arma__arma11 garch__garch11 gp_pois_regr__gp_pois_regr hmm_example__hmm_example '
          'bball_drive_event_0__hmm_drive_0 one_comp_mm_elim_abs__one_comp_mm_elim_abs hudson_lynx_hare__lotka_volterra '
          'mcycle_gp__accel_gp').split()
arms = os.environ.get('ARMS', 'default beyond-warmup adaptsel-warmup stan-search').split()
seeds = os.environ.get('SEEDS', '92101').split()
tag = os.environ.get('TAG', 'sweep')
exe = os.path.normpath(os.environ.get('EXE', S + '/target/release/warmup-gap-diag-v1.exe'))
lines = ['@echo off']
os.makedirs(f'{S}/{tag}', exist_ok=True)
for seed in seeds:
  for m in models:
    for a in arms:
        out = os.path.normpath(f'{S}/{tag}/{m}-{a}-{seed}.json')
        if os.path.exists(out):
            continue
        lines.append(f'"{exe}" "{os.path.normpath(M + "/" + m + "_model.so")}" "{os.path.normpath(M + "/" + m + ".data.json")}" {seed} "{out}" {a} >> "{os.path.normpath(S + "/" + tag + ".log")}" 2>&1')
lines.append(f'echo done > "{os.path.normpath(S + "/" + tag + ".done")}"')
with open(S + f'/{tag}.cmd', 'w', newline='\r\n') as f:
    f.write('\n'.join(lines) + '\n')
print(len(lines) - 2, 'cells')
