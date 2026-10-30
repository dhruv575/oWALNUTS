import hashlib,json,math
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';root=local/'step_ladder01'
s=json.loads((root/'SUMMARY.json').read_text());assert s['unchanged'] and len(s['rows'])==20
for p,h in s['inputs'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
models=['arK-arK','sblrc-blr','eight_schools-eight_schools_centered','garch-garch11','gp_pois_regr-gp_pois_regr'];core=['arK-arK','sblrc-blr','garch-garch11']
records={};audit=[]
for m in models:records[1.,m]=json.loads((local/'matched_geometry01'/m/'SUMMARY.json').read_text())
for row in s['rows']:
    factor,m=row['factor'],row['model'];assert (factor,m) not in records
    folder=root/row['folder'];sup=json.loads((folder/'SUPERVISION.json').read_text());assert sup['group_drained']
    if not row['completed']:records[factor,m]=None;continue
    r=json.loads((folder/'SUMMARY.json').read_text());base=records[1.,m]
    assert r['native']==base['native']
    for p,h in r['inputs'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
    inp=json.loads((folder/'INPUT.json').read_text());old=json.loads((local/'matched_geometry01'/m/'INPUT.json').read_text());output=json.loads((folder/'OUTPUT.json').read_text())
    assert inp['draws']==old['draws']==2000 and len(inp['chains'])==4
    for c,b,o in zip(inp['chains'],old['chains'],output['chains']):
        assert c['mass']==b['mass'] and c['start']==b['start'] and c['seed']==b['seed']
        assert c['step_size']==b['step_size']*factor
        assert abs(o['step_size']-c['step_size'])<=math.ulp(c['step_size'])
        assert len(o['mass'])==len(c['mass']) and all(abs(a-b)<=math.ulp(b) for a,b in zip(o['mass'],c['mass']))
    assert r['walnuts']['continuation_calls']==output['target_calls']==sum(c['target_calls'] for c in output['chains'])
    pilot=base['walnuts']['workflow_calls']-base['walnuts']['continuation_calls'];assert r['walnuts']['workflow_calls']==pilot+output['target_calls']
    if r['qualified_ratios'] is not None:
        assert r['native']['passed'] and r['walnuts']['passed']
        for key,cost in [('efficiency','continuation_calls'),('workflow_efficiency','workflow_calls')]:
            val=(r['walnuts']['bulk']/r['walnuts'][cost])/(r['native']['bulk']/r['native'][cost]);assert val==r['qualified_ratios'][key]
    records[factor,m]=r;audit.append(dict(model=m,factor=factor,settings_and_costs_verified=True))
assert len(records)==25
for record in records.values():
    if record is None:continue
    for arm in ['native','walnuts']:
        r=record[arm];keys=['rhat','bulk','tail','divergences','max_z','max_mean_sd','max_sd_error']
        finite=all(r[k] is not None and math.isfinite(r[k]) for k in keys)
        passed=finite and r['rhat']<=1.01 and r['bulk']>=400 and r['tail']>=400 and r['divergences']==0 and r['max_z']<=4.5 and r['max_mean_sd']<=.1 and r['max_sd_error']<=.1
        assert bool(passed)==r['passed']
rows=[];choices=[]
for factor in [.5,1.,2.,4.,8.]:
    losses=[m for m in models if records[1.,m]['walnuts']['passed'] and (records[factor,m] is None or not records[factor,m]['walnuts']['passed'])]
    valid=all(records[factor,m] is not None and records[factor,m]['qualified_ratios'] is not None for m in core)
    gains={m:records[factor,m]['qualified_ratios']['workflow_efficiency'] for m in core} if valid else None
    gm=math.exp(sum(math.log(v) for v in gains.values())/3) if valid else None
    eligible=bool(valid and not losses and gm>=1.2 and gains['garch-garch11']>=1.2 and min(gains.values())>=.9)
    if eligible:choices.append((gm,-abs(math.log2(factor)),factor))
    rows.append(dict(factor=factor,paired_accuracy_losses=losses,core_workflow_ratios=gains,core_geometric_mean=gm,eligible_for_fresh_replication=eligible))
selected=max(choices)[2] if choices else None
out=dict(selected_factor=selected,factors=rows,audits=audit,scope='Exposed tuning selection, not confirmation.',cells=[dict(factor=f,model=m,result=r) for (f,m),r in records.items()])
(study/'STEP-LADDER-ANALYSIS.json').write_text(json.dumps(out,indent=2)+'\n')
lines=['# Exposed step-size ladder','',out['scope'],'','| Factor | arK workflow ratio | Regression workflow ratio | GARCH workflow ratio | Core geometric mean | Accuracy losses | Eligible |','|---|---|---|---|---|---|---|']
for r in rows:
    gains=r['core_workflow_ratios'];vals=[f"{gains[m]:.3f}" for m in core]+[f"{r['core_geometric_mean']:.3f}"] if gains else ['unqualified']*4
    lines.append('| '+str(r['factor'])+' | '+' | '.join(vals)+' | '+str(r['paired_accuracy_losses'])+' | '+str(r['eligible_for_fresh_replication'])+' |')
lines+=['','Selected multiplier for a possible fresh replication: '+str(selected)+'.','ARMA remains a failed recovery. All five recoverable targets, including both guards, are preserved in JSON. Ratios require both accuracy gates. Full workflow includes native learning/recovery costs. No wall-time claim. No significance claim from selecting among exposed factors.']
(study/'STEP-LADDER-REPORT.md').write_text('\n'.join(lines)+'\n');print(json.dumps(dict(selected_factor=selected,factors=rows)))
