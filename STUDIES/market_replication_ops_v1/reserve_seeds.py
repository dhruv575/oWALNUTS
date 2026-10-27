"""Reserve complete native raw/derived seeds by pure integer arithmetic; no RNG."""
import argparse,hashlib,json
from pathlib import Path
from seed_derivation_snapshot import native_roles,flatten,combined
MONTHS=[('2026-04',1440),('2026-05',1488),('2026-06',1440)]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def reserve(main):
    main=Path(main);e61path=main/'STUDIES/prior_predictive_validation_v1/SEED-AUDIT.json';pastpath=main/'STUDIES/long_horizon_k400_v1/SEED-RESERVATIONS.json';devpath=main/'STUDIES/prior_predictive_validation_v1/DEVELOPMENT-SEEDS.json'
    e61=json.loads(e61path.read_bytes());past=json.loads(pastpath.read_bytes());dev=json.loads(devpath.read_bytes());reproduced=combined(e61)
    if reproduced['roles']!=past['long_roles'] or reproduced['real_roles']!=past['real_roles']:raise ValueError('Historical derivation reproduction differs')
    historical={'E61':flatten(e61['roles']),'E62':flatten(past['real_roles']),'E63':flatten(past['long_roles']),'development_E61':flatten(native_roles(dev['initial'],dev['warm'],32))|{dev['reference_sample'],dev['reference_model']},'development_independent_and_long_literal':flatten(native_roles(99371041,99371042,4))|{99371041,99371042,99371043}}
    roles={};configuration=[];sets={};collisions={}
    for m,(month,n) in enumerate(MONTHS):
        initial=2026102801000000+100000*m;warm=2026102802000000+100000*m;bootstrap=2026102803000000+100000*m;base=502710000+100000*m
        group=native_roles(initial,warm,n);group['bootstrap']=[bootstrap];group['reference_sample_and_model']=[base+1000*j+k for j in range(8) for k in range(2)];roles[month]=group;sets[month]=flatten(group)
        flat=[x for v in group.values() for x in v]
        if len(flat)!=len(set(flat)):raise ValueError('Unexpected within-month seed alias '+month)
        configuration.append(dict(month=month,updates=n,initial=initial,warm=warm,bootstrap=bootstrap,reference_base=base,reference_stride=1000,reference_count=8,model_seed_offset=1))
    for name,new in sets.items():
        for old,values in historical.items():
            shared=sorted(new&values)
            if shared:collisions[name+'__'+old]=shared
    for i,(a,_) in enumerate(MONTHS):
        for b,_ in MONTHS[i+1:]:
            shared=sorted(sets[a]&sets[b])
            if shared:collisions[a+'__'+b]=shared
    if collisions:raise ValueError('Seed collisions '+repr(collisions))
    return dict(status='reserved_no_rng_consumed',months=configuration,month_roles=roles,historical_counts={k:len(v) for k,v in historical.items()},new_unique=len(set.union(*sets.values())),collisions=collisions,inputs={str(p):sha(p) for p in (e61path,pastpath,devpath)},derivation_sha256=sha(Path(__file__).with_name('seed_derivation_snapshot.py')),limits='Explicit E61/E62/E63 inventories and known full-worker development schedules. Opaque nutpie internal chain derivations are not claimed; public scalar sample/model seeds are reserved. Bounded source/metadata lexical audit is separate.')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('main');p.add_argument('output');a=p.parse_args();result=reserve(a.main)
    with Path(a.output).open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({k:result[k] for k in ('status','months','historical_counts','new_unique','collisions')}))
