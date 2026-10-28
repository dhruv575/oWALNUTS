"""Bind prepared inputs to the pre-outcome freeze without changing scientific rules."""
import hashlib,json,sys
from pathlib import Path

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def run(lane):
    lane=Path(lane).resolve();out=lane/'FREEZE.json'
    if out.exists():raise FileExistsError('Sampling already admitted; inspect existing freeze')
    prior=json.loads((lane/'PRE-ACQUISITION.json').read_text());sources=dict(prior['sources'])
    supervision=json.loads((lane/'preparation-monitor/SUPERVISION.json').read_text())
    if supervision.get('exit_code')!=0 or not supervision.get('group_drained') or not supervision.get('sources_unchanged'):raise ValueError('Preparation supervision')
    prep=json.loads((lane/'fixtures/PREPARATION.json').read_text())
    if prep['origins']!=2928 or prep['baseline_slots']!=8784:raise ValueError('Denominator')
    if sha(lane/'ACQUISITION-BINDINGS.json')!=prep['bindings_sha256']:raise ValueError('Acquisition binding')
    if sha(lane/'CALENDAR.json')!=prior['calendar_sha256']:raise ValueError('Calendar drift')
    for name,meta in prep['files'].items():
        p=lane/'fixtures'/name
        if not p.resolve().is_relative_to(lane/'fixtures') or p.stat().st_size!=meta['bytes']:raise ValueError('Prepared path/size')
        sources[p.relative_to(lane).as_posix()]=meta['sha256']
    for name,h in sources.items():
        p=(lane/name).resolve()
        if not p.is_relative_to(lane) or sha(p)!=h:raise ValueError('Frozen source/input mismatch')
    fixtures=json.loads((lane/'fixtures/FIXTURES.json').read_text());labels=json.loads((lane/'fixtures/LABELS.json').read_text());baselines=json.loads((lane/'fixtures/BASELINES.json').read_text())
    if [r['index'] for r in fixtures]!=list(range(2928)) or [r['index'] for r in labels]!=list(range(2928)):raise ValueError('Fixture/label identity')
    expected={(i,m) for i in range(2928) for m in ['rolling_t5','ewma_t5','nig_ar1']}
    if len(baselines)!=len(expected) or {(r['index'],r['method']) for r in baselines}!=expected:raise ValueError('Baseline slots')
    calendar=json.loads((lane/'CALENDAR.json').read_text())['cells']
    if len(calendar)!=3050:raise ValueError('Calendar denominator')
    for c in calendar:
        i=(0 if c['month']=='2025-09' else 1440)+c['tick']-1;r=fixtures[i]
        for k in ['month','tick','origin_ms','label_available_ms','label_index']:
            if c[k]!=r[k]:raise ValueError('Calendar/fixture alignment')
    for name in ['PRE-ACQUISITION.json','CALENDAR.json','ACQUISITION-BINDINGS.json','fixtures/PREPARATION.json','preparation-monitor/SUPERVISION.json']:sources[name]=sha(lane/name)
    frozen=dict(status='admitted',cells=3050,sources=sources,versions=prior['versions'],binaries=prior['binaries'],pre_acquisition_sha256=sha(lane/'PRE-ACQUISITION.json'),admission_runner_sha256=sha(__file__),scope='Fixed historical project-access confirmation; failed slots retained; not economic qualification')
    with out.open('x') as f:json.dump(frozen,f,indent=2);f.write('\n')
    print(json.dumps(dict(sampling_admitted=True,cells=3050,freeze_sha256=sha(out))),flush=True)

if __name__=='__main__':run(sys.argv[1])
