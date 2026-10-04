"""Diagnostic replay only: pilot outputs never become prospective bank fits."""
import argparse,json,sys,time
from pathlib import Path

def run(study,out):
    s=Path(study).resolve();sys.path.insert(0,str(s))
    from posterior_resource.bank_adapter import admit_fit,sha
    root=s/'artifacts/posterior-resource-pilot-v1';plan=json.loads((root/'plan.json').read_text());results=[]
    for i in [1,2]:
        c=plan['cells'][i];d=Path(c['out']);r=json.loads((d/'resource-result.json').read_text());worker=d/'fit/report.json';w=json.loads(worker.read_text());raw=d/'fit/draws-8000-raw.json'
        spec=dict(directory=str(d),id=c['id'],backend=c['backend'],sampler_seed=c['seed'],initialization_seed=c['init_seed'],fixture=c['fixture'],fixture_sha256=c['fixture_sha256'],worker_report=str(worker),worker_report_sha256=sha(worker),result_sha256=sha(d/'resource-result.json'),compact_sha256=r['extraction']['compact_sha256'],raw=str(raw),raw_sha256=r['extraction']['raw_sha256'],resource_plan=str(root/'plan.json'),resource_plan_sha256=sha(root/'plan.json'),study=str(s),initialization_helper_sha256=sha(s/'masked_market_comparison_plan.py'),worker_bindings=w['bindings'],predictive_contract=r['extraction']['predictive_contract'])
        tick=time.perf_counter();a=admit_fit(spec,plan['posterior_sha256']);results.append(dict(id=c['id'],status='diagnostic_admission_passed',seconds=time.perf_counter()-tick,predictive_cache_admitted=a['predictive_cache_admitted'],qualified=a['qualified'],pilot_excluded_from_prospective_bank=True,raw_sha256=spec['raw_sha256']))
    evidence=dict(results=results,source_sha256=sha(s/'posterior_resource/bank_adapter.py'),script_sha256=sha(__file__),sampling=False,scope='Diagnostic validation only; no bank collection or pilot stream reuse')
    with Path(out).open('x') as f:json.dump(evidence,f,indent=2)
    print(json.dumps(evidence))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--study',required=True);p.add_argument('--out',required=True);a=p.parse_args();run(a.study,a.out)
