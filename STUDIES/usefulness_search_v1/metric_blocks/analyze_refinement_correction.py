import hashlib,json,math
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';entries=[]
for name,count in [('refinement_ablation01',15),('refinement_ablation02',10)]:
    root=local/name;s=json.loads((root/'SUMMARY.json').read_text());assert len(s['rows'])==count and s['unchanged']
    for p,h in s['inputs'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
    entries.extend((root,r) for r in s['rows'])
for root,r in entries:
    if r['levels']==8 and r['max_error']==1:assert r['completed'], 'Baseline parity must pass before interpretation'

def qualified(r):
    keys=['rhat','bulk','tail','divergences','max_z','max_mean_sd','max_sd_error'];finite=all(r[k] is not None and math.isfinite(r[k]) for k in keys)
    return bool(finite and r['rhat']<=1.01 and r['bulk']>=400 and r['tail']>=400 and r['divergences']==0 and r['max_z']<=4.5 and r['max_mean_sd']<=.1 and r['max_sd_error']<=.1)
rows=[];outputs={}
for root,entry in entries:
    m=entry['model'];folder=root/entry['folder'];sup=json.loads((folder/'SUPERVISION.json').read_text());assert sup['group_drained']
    if not entry['completed']:rows.append(dict(**entry,error='worker_failed'));continue
    r=json.loads((folder/'SUMMARY.json').read_text());base=json.loads((local/'matched_geometry01'/m/'SUMMARY.json').read_text());assert r['native']==base['native']
    for p,h in r['inputs'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
    for arm in ['native','walnuts']:assert r[arm]['passed']==qualified(r[arm])
    inp=json.loads((folder/'INPUT.json').read_text());old=json.loads((local/'matched_geometry01'/m/'INPUT.json').read_text());assert inp['chains']==old['chains'] and inp['draws']==old['draws']==2000
    result=json.loads((folder/'OUTPUT.json').read_text());outputs[m,entry['levels'],entry['max_error']]=result
    for c in result['chains']:
        assert c['levels']==entry['levels'] and c['max_error']==entry['max_error']
        assert c['work']['all_phase_calls']==c['target_calls']
        if entry['levels']==1:assert c['work']['target_calls_reverse']==0
    assert r['walnuts']['continuation_calls']==sum(c['target_calls'] for c in result['chains'])==result['target_calls']
    native_ratio=r['qualified_ratios'];baseline_ratio=None
    if r['walnuts']['passed'] and base['walnuts']['passed']:
        baseline_ratio={k:r['walnuts'][k]/base['walnuts'][k] for k in ['efficiency','workflow_efficiency']}
    rows.append(dict(**entry,native_pass=r['native']['passed'],walnuts=r['walnuts'],native_ratios=native_ratio,baseline_walnuts_ratios=baseline_ratio,accuracy_loss=base['walnuts']['passed'] and not r['walnuts']['passed'],reverse_calls=sum(c['work']['target_calls_reverse'] for c in result['chains']),exhaustion_stops=sum(c['work']['refinement_exhaustion_stops'] for c in result['chains'])))
parity=[]
for m in sorted({r['model'] for r in rows}):
    if (m,1,1000.) in outputs and (m,8,1000.) in outputs:
        a,b=outputs[m,1,1000.],outputs[m,8,1000.]
        same=all(x['draws']==y['draws'] and x['target_calls']==y['target_calls'] for x,y in zip(a['chains'],b['chains']))
        parity.append(dict(model=m,permissive_levels_exact_draw_and_call_parity=same))
out=dict(rows=rows,permissive_level_comparisons=parity,scope='Corrected one-versus-eight-level exposed factorial; two-level rows are auxiliary. Not independent validation or standard-NUTS equivalence.')
(study/'REFINEMENT-CORRECTED-ANALYSIS.json').write_text(json.dumps(out,indent=2)+'\n')
lines=['# Refinement/error-threshold ablation','',out['scope'],'','| Target | Levels | Error threshold | WALNUTS pass | Native continuation ratio | Baseline WALNUTS continuation ratio | Reverse calls |','|---|---|---|---|---|---|---|']
for r in rows:
    n=r.get('native_ratios');b=r.get('baseline_walnuts_ratios');lines.append(f"| {r['model']} | {r['levels']} | {r['max_error']} | {r.get('walnuts',{}).get('passed','worker failed')} | "+(f"{n['efficiency']:.3f}" if n else 'unqualified')+' | '+(f"{b['efficiency']:.3f}" if b else 'unqualified')+f" | {r.get('reverse_calls','unavailable')} |")
lines+=['','Full workflow ratios, all diagnostics and failures are preserved in JSON. Both accuracy gates are required for each ratio. No runtime comparison or default recommendation.','', 'Permissive-level exact comparisons: '+json.dumps(parity)+'.']
(study/'REFINEMENT-CORRECTED-REPORT.md').write_text('\n'.join(lines)+'\n');print(json.dumps(dict(completed=sum(r['completed'] for r in rows),permissive_parity=parity)))
