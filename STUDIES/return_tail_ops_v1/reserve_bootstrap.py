"""Pure integer inventory plus bounded source-token audit; never initializes RNG."""
import argparse,hashlib,json,re,subprocess,time
from pathlib import Path

def ints(value):
    if type(value) is int:yield value
    elif isinstance(value,dict):
        for item in value.values():yield from ints(item)
    elif isinstance(value,list):
        for item in value:yield from ints(item)

def reserve(main):
    main=Path(main);seeds={'2026-04':2026102804000000,'2026-05':2026102804100000,'2026-06':2026102804200000}
    inputs={};existing=set()
    for name in ('prior_predictive_validation_v1/SEED-AUDIT.json','prior_predictive_validation_v1/DEVELOPMENT-SEEDS.json','long_horizon_k400_v1/SEED-RESERVATIONS.json','market_replication_ops_v1/SEED-RESERVATIONS.json'):
        p=main/'STUDIES'/name;raw=p.read_bytes();inputs[name]=hashlib.sha256(raw).hexdigest();existing.update(ints(json.loads(raw)))
    collision=sorted(set(seeds.values())&existing)
    if collision:raise ValueError('Reserved inventory collision '+repr(collision))
    start=time.monotonic();checked=0;skipped=0;hits=[];stop=None
    names=subprocess.check_output(['git','ls-files','-z'],cwd=main).decode().split('\0')
    token=re.compile(r'(?<![\w.])\d[\d_]*(?![\w.])')
    for name in names:
        p=Path(name)
        if p.suffix.lower() not in ('.py','.rs','.md','.toml','.yaml','.yml','.json'):continue
        if any(part.lower() in ('target','artifacts','evidence','node_modules','.venv','venv') or part.lower().startswith('execution-') for part in p.parts):continue
        if p.suffix.lower()=='.json' and not any(x in p.name.lower() for x in ('seed','manifest','protocol','draft','config','plan')):continue
        if time.monotonic()-start>30 or checked>=5000:stop='time_or_file_bound';break
        path=main/p
        if not path.is_file() or path.stat().st_size>2*1024*1024:skipped+=1;continue
        text=path.read_text(encoding='utf-8',errors='replace');checked+=1
        found={int(m.group().replace('_','')) for m in token.finditer(text)}&set(seeds.values())
        if found:hits.append(dict(path=name,seeds=sorted(found)))
        if len(hits)>=100:stop='hit_bound';break
    return dict(status='reserved_no_rng_consumed',bootstrap=seeds,inventory_inputs_sha256=inputs,inventory_collisions=collision,
        bounded_source_audit=dict(checked_files=checked,skipped_missing_or_oversized=skipped,elapsed_seconds=time.monotonic()-start,stop=stop,hits=hits,max_seconds=30,max_files=5000,max_file_bytes=2097152,scope='Tracked project source/docs and named metadata; excludes raw/evidence/build directories. Exact integer tokens, no raw matching lines. Explicit inventories independently cover large seed metadata; not a universal collision proof.'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('main');p.add_argument('output');a=p.parse_args();result=reserve(a.main)
    with Path(a.output).open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result))
