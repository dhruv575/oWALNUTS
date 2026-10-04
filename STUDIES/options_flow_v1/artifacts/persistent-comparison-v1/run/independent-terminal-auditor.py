"""Independent terminal review; do not execute during measured campaign."""
import argparse, hashlib, json, math, sys, zipfile
from pathlib import Path

PIN = '924569d7d03cd9eadd9e86268da4b2d6577e2d78ce9b39536cde3b50b44271e6'
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def load(path):return json.loads(Path(path).read_text())
def gate(r,fixture):
    if r.get('status')!='completed':return False
    e=r['evaluation'];fs=e['functionals'];qs=e['canonical_parameter_diagnostics']
    def health(v):return all(math.isfinite(v[k]) for k in ['rhat','bulk_ess','tail_ess']) and 0<v['rhat']<=1.01 and min(v['bulk_ess'],v['tail_ess'])>=400
    def precise(b,m):return len(b)==len(m)==2 and all(math.isfinite(v) for v in b+m) and b[1]>b[0] and min(m)>=0 and max(m)<=.02*(b[1]-b[0])
    rows=e['forecast']['rows'];available=[v for v in rows if v['forecast_available']]
    assert len(fs)==14 and len(qs)==140 and len(rows)==4
    assert {(v['horizon'],v['group']) for v in available}=={tuple(v) for v in fixture['forecast_cells']}
    return r['retained_divergences']==0 and all(health(v) for v in [*fs.values(),*qs.values()]) and all(precise(v['interval_90'],v['endpoint_mcse']) for v in fs.values()) and all(precise([v['lower'],v['upper']],v['endpoint_mcse']) for v in available)

def main(directory):
    directory=Path(directory).resolve();p=load(directory/'plan.json');checks={};errors={};inventory={}
    def check(name,value):checks[name]=bool(value)
    def attempt(name,fn):
        try:fn();check(name,True)
        except Exception as exc:check(name,False);errors[name]=repr(exc)
    check('pinned_plan',sha(directory/'plan.json')==PIN== (directory/'plan.sha256').read_text().strip())
    check('reviewed_draft',sha(directory/'plan-draft.json')==p['reviewed_draft_sha256'])
    # Resolve source from its explicitly bound controller, avoiding argv offsets.
    study=next(Path(k).parent for k in p['study_bindings'] if Path(k).name=='persistent_comparison_plan.py')
    sys.path.insert(0,str(study))
    from persistent_comparison_plan import validate_plan,validate_fit,timing_report
    from asof_rolling_execute import validate_hardware
    attempt('recipe_validation',lambda:validate_plan(p,directory))
    for category in ['bound_files','study_bindings']:
        for path,h in p[category].items():check(category+':'+path,sha(path)==h)
    summary=load(directory/'execution-summary.json');byid={r['id']:r for r in summary['cohorts']}
    check('four_unique_cohorts',len(summary['cohorts'])==len(byid)==4 and set(byid)=={c['id'] for c in p['cohorts']})
    allfits=[]
    for c in p['cohorts']:
        cid=c['id'];r=byid[cid];base=directory/cid;status=load(directory/(cid+'-status.json'))
        check(cid+':status_match',r==status)
        check(cid+':started_binding',load(directory/(cid+'-started.json'))==dict(plan_sha256=PIN,cohort=c))
        h=load(directory/(cid+'-hardware.json'))
        attempt(cid+':hardware',lambda:validate_hardware(h,c['command'],r['returncode'],1800))
        check(cid+':exit_retained',load(directory/(cid+'-exit.json'))['returncode']==r['returncode'])
        check(cid+':cost',math.isfinite(r['elapsed_seconds']) and r['elapsed_seconds']>0)
        reports=[]
        for i,fitid in enumerate(c['fit_ids']):
            folder=base/f'fit-{i}';path=folder/'report.json';entry=dict(id=fitid,usable=False)
            if path.exists():
                report=load(path);fixture=p['fixtures'][c['fixture_indices'][i]];reports.append(report)
                attempt(fitid+':transport_and_tiers',lambda:validate_fit(report,fixture,c['seeds'][i],c['backend'],folder))
                independent=gate(report,fixture);entry.update(usable=independent,status=report['status'],report_sha256=sha(path),draws=[a['draws'] for a in report.get('attempts',[])])
                check(fitid+':reported_gate',independent==report.get('precision_pass',False))
                check(fitid+':summary_gate',independent==r['fits'][i].get('independently_validated_precision_pass',False))
                if report['status']=='completed':
                    check(fitid+':fresh_policy',report['fresh_adaptation'] is True and report['posterior_continuation'] is False)
                    check(fitid+':starts',report['initial_positions']==fixture['starts'])
                    if c['backend']=='pymc':check(fitid+':native_parity',report['native_parity']['passed'] is True)
                    else:check(fitid+':reset',report['warmup_admission']['previous_posterior_state_cleared'] is True and report['warmup_iterations']==[1000]*4)
                for raw in folder.rglob('raw.json'):inventory[str(raw)]=dict(sha256=sha(raw),bytes=raw.stat().st_size)
            else:
                entry['status']='missing';check(fitid+':missing_accounted',r['fits'][i]['usable'] is False and r['returncode']!=0)
            allfits.append(entry)
        if len(reports)==3 and all('common_logp' in x for x in reports):
            check(cid+':ABA_target',reports[0]['common_logp']==reports[2]['common_logp'] and reports[0]['common_gradient']==reports[2]['common_gradient'])
            check(cid+':B_target_changed',reports[0]['common_logp']!=reports[1]['common_logp'] or reports[0]['common_gradient']!=reports[1]['common_gradient'])
    check('twelve_fits',len(allfits)==12)
    timing=timing_report(summary,directory);check('timing_recomputed',timing==load(directory/'timing-report.json'))
    out=dict(integrity_pass=all(checks.values()),plan_sha256=PIN,checks=checks,errors=errors,fits=allfits,timing=timing,raw_inventory=inventory,qualified=False,limitations=['Two fixed sparse market posteriors and paired streams; not calibration or market utility evidence.','Full cohort ratios require all three fits on both arms to pass; failed/missing work remains in denominator.','Controller transport validation reused, with independent final health/precision gate and normalized parity/reset checks.'])
    with (directory/'independent-terminal-audit.json').open('x') as f:json.dump(out,f,indent=2)
    source=Path(__file__);copy=directory/'independent-terminal-auditor.py'
    with copy.open('xb') as f:f.write(source.read_bytes())
    with zipfile.ZipFile(directory/'independent-terminal-study-source.zip','x',zipfile.ZIP_DEFLATED) as z:
        for path in p['study_bindings']:z.write(path,Path(path).name)
    provenance=dict(auditor_sha256=sha(copy),source_zip_sha256=sha(directory/'independent-terminal-study-source.zip'),result_sha256=sha(directory/'independent-terminal-audit.json'),plan_sha256=PIN,runtime=p['runtime'],bound_runtime_files={k:v for k,v in p['bound_files'].items() if k.endswith(('.exe','.pyd','__init__.py'))})
    with (directory/'independent-terminal-provenance.json').open('x') as f:json.dump(provenance,f,indent=2)
    print(json.dumps(dict(integrity_pass=out['integrity_pass'],failed_checks=[k for k,v in checks.items() if not v],usable=sum(r['usable'] for r in allfits),paired_ratios=timing['paired_ratios'])))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('directory');main(ap.parse_args().directory)
