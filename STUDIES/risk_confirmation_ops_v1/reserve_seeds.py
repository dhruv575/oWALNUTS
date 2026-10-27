"""Pure integer full seed reservation; no RNG or model/data calls."""
import argparse,hashlib,json,re,subprocess,time
from pathlib import Path
from seed_derivation_snapshot import native_roles,flatten
MONTHS=(('2025-12',1488),('2026-01',1488),('2026-02',1344))

def integers(v):
    if type(v)is int:yield v
    elif isinstance(v,dict):
        for x in v.values():yield from integers(x)
    elif isinstance(v,list):
        for x in v:yield from integers(x)

def reserve(main):
    main=Path(main);historical={};inputs={}
    for name in ('prior_predictive_validation_v1/SEED-AUDIT.json','prior_predictive_validation_v1/DEVELOPMENT-SEEDS.json','long_horizon_k400_v1/SEED-RESERVATIONS.json','market_replication_ops_v1/SEED-RESERVATIONS.json','return_tail_ops_v1/BOOTSTRAP-RESERVATIONS.json'):
        raw=(main/'STUDIES'/name).read_bytes();inputs[name]=hashlib.sha256(raw).hexdigest();historical[name]=set(integers(json.loads(raw)))
    # Extra explicitly known literal-only development schedule from the independent-engine preflight.
    historical['known_literal_preflight']=flatten(native_roles(99371041,99371042,4))|{99371041,99371042,99371043,17}
    configs=[];roles={};sets={}
    for index,(month,count) in enumerate(MONTHS):
        initial=2026102901000000+100000*index;warm=2026102902000000+100000*index;bootstrap=2026102903000000+100000*index;ref=602710000+100000*index
        group=native_roles(initial,warm,count);group['bootstrap']=[bootstrap];group['reference_sample_and_model']=[ref+1000*i+j for i in range(8) for j in range(2)]
        values=list(integers(group));assert len(values)==len(set(values)),month
        roles[month]=group;sets[month]=set(values);configs.append(dict(month=month,origins=count,initial=initial,warm=warm,bootstrap=bootstrap,reference_base=ref,reference_stride=1000,reference_count=8,model_seed_offset=1))
    for name,values in sets.items():
        for old,previous in {**historical,**{k:v for k,v in sets.items() if k!=name}}.items():
            if values&previous:raise ValueError('Seed collision '+name+' / '+old)
    allnew=set.union(*sets.values());start=time.monotonic();checked=0;skipped=0;hits=[];stop=None;token=re.compile(r'(?<![\w.])\d[\d_]*(?![\w.])')
    for name in subprocess.check_output(['git','ls-files','-z'],cwd=main).decode().split('\0'):
        p=Path(name)
        if p.suffix.lower() not in ('.py','.rs','.md','.toml','.yaml','.yml','.json'):continue
        if any(part.lower() in ('target','artifacts','evidence','node_modules','.venv','venv') or part.lower().startswith('execution-') for part in p.parts):continue
        if p.suffix.lower()=='.json' and not any(x in p.name.lower() for x in ('seed','manifest','protocol','draft','config','plan')):continue
        if time.monotonic()-start>30 or checked>=5000:stop='fixed_time_or_file_bound';break
        path=main/p
        if not path.is_file() or path.stat().st_size>2097152:skipped+=1;continue
        text=path.read_text(encoding='utf-8',errors='replace');checked+=1;found={int(m.group().replace('_','')) for m in token.finditer(text)}&allnew
        if found:hits.append(dict(path=name,matching_seed_count=len(found),first_ten=sorted(found)[:10]))
        if len(hits)>=100:stop='fixed_hit_bound';break
    return dict(status='reserved_no_rng_consumed',months=configs,month_roles=roles,new_unique=len(allnew),collisions=[],inventory_inputs_sha256=inputs,known_inventory_counts={k:len(v) for k,v in historical.items()},derivation_sha256=hashlib.sha256(Path(__file__).with_name('seed_derivation_snapshot.py').read_bytes()).hexdigest(),bounded_metadata_audit=dict(checked_files=checked,skipped_missing_or_oversized=skipped,elapsed_seconds=time.monotonic()-start,hits=hits,stop=stop,max_seconds=30,max_files=5000,max_file_bytes=2097152,scope='Tracked main source/docs and named metadata only; excludes raw/build/execution payloads. Explicit historical inventories audited separately. Exact integer tokens, bounded path/count output. Opaque internal independent-engine chain RNG derivations are not claimed.'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('main');p.add_argument('out');a=p.parse_args();v=reserve(a.main)
    with Path(a.out).open('x') as f:json.dump(v,f,indent=2);f.write('\n')
    print(json.dumps({k:v[k] for k in ('months','new_unique','collisions','bounded_metadata_audit')}))
