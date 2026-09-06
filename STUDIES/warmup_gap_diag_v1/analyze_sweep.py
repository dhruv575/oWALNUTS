"""Score the warmup candidate sweep: per model x arm, warmup gradients, adapted step, crashes,
min bulk ESS over unconstrained coordinates (ArviZ), ESS per gradient (total and sampling-only),
ratios against the default arm, and geomeans."""
import glob, json, math, os, sys
import numpy as np
import arviz as az

S = os.environ.get("SWEEP_ROOT", os.path.dirname(os.path.abspath(__file__)))
TAG = sys.argv[1] if len(sys.argv) > 1 else 'sweep'
ARMS = sys.argv[2].split(',') if len(sys.argv) > 2 else ['default', 'beyond-warmup', 'adaptsel-warmup', 'stan-search']
TARGETS = {'eight_schools__eight_schools_noncentered', 'eight_schools__eight_schools_centered', 'gp_pois_regr__gp_pois_regr', 'mcycle_gp__accel_gp'}


def score(path):
    o = json.load(open(path))
    draws = np.array([c['draws'] for c in o['chains']])  # chains x draws x dim
    ess = az.ess(az.convert_to_dataset(draws[:, :, :]), method='bulk')
    ess = np.array(ess.to_array()).reshape(-1)
    rhat = np.array(az.rhat(az.convert_to_dataset(draws), method='rank').to_array()).reshape(-1)
    wu = sum(c['warmup_calls'] for c in o['chains'])
    sp = sum(c['retained_calls'] for c in o['chains'])
    h = float(np.median([c['final_step'] for c in o['chains']]))
    crashes = 0
    for c in o['chains']:
        cp = c['checkpoints']
        st = np.array([d[1] for d in c['diagnostics'][:1000]])
        hb = np.array([x['h_before'] for x in cp]); ha = np.array([x['h_after'] for x in cp]); rr = np.array([x['rc_rej'] for x in cp])
        crashes += int(((st == 1) & (rr >= 1) & (ha < hb / 2)).sum())
    div = sum(c['retained_divergences'] for c in o['chains'])
    rcs = sum(c['retained_rc_stops'] for c in o['chains'])
    return dict(wu=wu, sp=sp, h=h, crashes=crashes / 4, ess=float(ess.min()), rhat=float(rhat.max()), div=div,
                rc_stop_frac=rcs / 4000, epg=float(ess.min()) / (wu + sp), epg_s=float(ess.min()) / sp)


rows = {}
for f in sorted(glob.glob(f'{S}/{TAG}/*.json')):
    name = os.path.basename(f)[:-5]
    parts = name.rsplit('-', 1)
    if len(parts) == 2 and parts[1].isdigit():
        name = parts[0]
    for a in ARMS:
        if name.endswith('-' + a):
            m = name[: -len(a) - 1]
            sc = score(f)
            cur = rows.setdefault(m, {}).setdefault(a, [])
            cur.append(sc)
            break
# seed medians per field
for m, arms in rows.items():
    for a, lst in arms.items():
        arms[a] = {k: float(np.median([x[k] for x in lst])) for k in lst[0]}

g = lambda xs: math.exp(np.mean(np.log(xs))) if xs else float('nan')
print(f"{'model':30s} " + ' '.join(f'{a[:14]:>32s}' for a in ARMS))
print(f"{'':30s} " + ' '.join(f"{'wu/sp  h  crash rhat | epg  epg_s':>32s}" for a in ARMS))
ratios = {a: {'epg': [], 'epg_s': [], 'wu': [], 'h': []} for a in ARMS}
for m, arms in rows.items():
    d = arms.get('default')
    line = f'{m[:30]:30s} '
    for a in ARMS:
        r = arms.get(a)
        if r is None:
            line += f"{'missing':>32s} "; continue
        if d and a != 'default':
            ratios[a]['epg'].append(r['epg'] / d['epg']); ratios[a]['epg_s'].append(r['epg_s'] / d['epg_s'])
            ratios[a]['wu'].append(r['wu'] / d['wu']); ratios[a]['h'].append(r['h'] / d['h'])
        rel = '' if (not d or a == 'default') else f" x{r['epg']/d['epg']:.2f}"
        line += f"{r['wu']/1000:6.0f}k/{r['sp']/1000:4.0f}k {r['h']:.3f} {r['crashes']:4.0f} {r['rhat']:.2f} |{r['epg']*1e3:6.2f} {r['epg_s']*1e3:6.2f}{rel:>6s} "
    print(line)
print()
for a in ARMS:
    if a == 'default': continue
    R = ratios[a]
    tg = [r for (m, arms), r in zip(rows.items(), R['epg']) if m in TARGETS]
    ct = [r for (m, arms), r in zip(rows.items(), R['epg']) if m not in TARGETS]
    print(f"{a:16s} vs default: ESS/grad geomean {g(R['epg']):.3f} (targets {g(tg):.3f}, controls {g(ct):.3f}); sampling-only {g(R['epg_s']):.3f}; warmup grads {g(R['wu']):.3f}; step {g(R['h']):.3f}; min {min(R['epg']):.2f} max {max(R['epg']):.2f}")
