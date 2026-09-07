"""Run profiler cells N-wide. Usage: python run_parallel.py <tag> <arms,comma> <seeds,comma> [models,comma|screen|full] [width]
Each cell uses 4 threads; width 4 fills 16 cores. Skips cells whose output exists."""
import os, sys, subprocess, itertools
from concurrent.futures import ThreadPoolExecutor
S = os.environ.get('SWEEP_ROOT', os.path.dirname(os.path.abspath(__file__)))
M = os.environ.get('MODELS', 'C:/dev/owalnuts-wt/posteriordb-v6/STUDIES/posteriordb_bench_v6/models')
FULL = ('eight_schools__eight_schools_noncentered eight_schools__eight_schools_centered diamonds__diamonds '
        'earnings__logearn_interaction mesquite__logmesquite_logvash kidiq__kidscore_momhsiq sblrc__blr nes2000__nes '
        'arK__arK arma__arma11 garch__garch11 gp_pois_regr__gp_pois_regr hmm_example__hmm_example '
        'bball_drive_event_0__hmm_drive_0 one_comp_mm_elim_abs__one_comp_mm_elim_abs hudson_lynx_hare__lotka_volterra '
        'mcycle_gp__accel_gp').split()
# screen: the four deciding targets plus five fast controls (no earnings/diamonds)
SCREEN = ('gp_pois_regr__gp_pois_regr mcycle_gp__accel_gp eight_schools__eight_schools_centered eight_schools__eight_schools_noncentered '
          'sblrc__blr kidiq__kidscore_momhsiq arK__arK arma__arma11 nes2000__nes').split()
tag, arms, seeds = sys.argv[1], sys.argv[2].split(','), sys.argv[3].split(',')
sel = sys.argv[4] if len(sys.argv) > 4 else 'full'
models = FULL if sel == 'full' else SCREEN if sel == 'screen' else sel.split(',')
width = int(sys.argv[5]) if len(sys.argv) > 5 else 4
exe = os.environ.get('EXE', f'{S}/target/release/warmup-gap-diag-v1.exe')
os.makedirs(f'{S}/{tag}', exist_ok=True)
def run(cell):
    m, a, seed = cell
    out = f'{S}/{tag}/{m}-{a}-{seed}.json'
    if os.path.exists(out): return
    with open(f'{S}/{tag}.log', 'a') as log:
        subprocess.run([exe, f'{M}/{m}_model.so', f'{M}/{m}.data.json', seed, out, a], stdout=log, stderr=log)
    print('done', m, a, seed, flush=True)
cells = list(itertools.product(models, arms, seeds))
# slowest first so the tail is short
order = {m: i for i, m in enumerate('earnings__logearn_interaction diamonds__diamonds mcycle_gp__accel_gp hudson_lynx_hare__lotka_volterra mesquite__logmesquite_logvash'.split())}
cells.sort(key=lambda c: order.get(c[0], 99))
with ThreadPoolExecutor(width) as ex: list(ex.map(run, cells))
open(f'{S}/{tag}.done', 'w').write('done\n')
