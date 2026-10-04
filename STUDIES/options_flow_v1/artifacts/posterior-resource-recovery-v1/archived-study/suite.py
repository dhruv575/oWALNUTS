"""Exploratory prior-generative replication launcher; no qualification shortcut."""
import argparse,json
from pathlib import Path
from model import simulate
from run import execute
from hardware_control import parse_cpus

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--exe',type=Path,required=True)
    p.add_argument('--seeds',required=True,help='Explicit comma-separated dataset and chain seeds; do not reuse frozen seeds')
    p.add_argument('--arms',default='numpyro-noncentered,noncentered');p.add_argument('--periods',type=int,default=128)
    p.add_argument('--groups',type=int,default=4);p.add_argument('--holdout',type=int,default=20)
    p.add_argument('--warmup',type=int,default=1000);p.add_argument('--draws',type=int,default=1000)
    p.add_argument('--timeout',type=float,default=1800)
    p.add_argument('--cpus',type=parse_cpus);p.add_argument('--require-attestation',action='store_true')
    p.add_argument('--reference-script',type=Path);a=p.parse_args()
    seeds=list(map(int,a.seeds.split(',')));arms=a.arms.split(',')
    if len(seeds)!=len(set(seeds)):raise ValueError('Duplicate seeds are not independent replicates')
    if len(arms)!=len(set(arms)):raise ValueError('Duplicate arms')
    a.out.mkdir(parents=True,exist_ok=True);manifest=a.out/'manifest.json'
    with manifest.open('x') as stream:json.dump({'phase':'exploratory','seeds':seeds,'arms':arms,'periods':a.periods,'groups':a.groups,'warmup':a.warmup,'draws':a.draws,
        'cpus':a.cpus,'require_attestation':a.require_attestation,'reference_script':str(a.reference_script) if a.reference_script else None,
        'order':'Rotate arm order by dataset index; every cell remains in expected denominator',
        'intended_cells':[{'seed':s,'arm':arm,'report':f'{s}/{arm}-report.json'} for s in seeds for arm in arms]},stream,indent=2)
    for index,seed in enumerate(seeds):
        out=a.out/str(seed);out.mkdir(parents=True,exist_ok=True);fixture=out/'fixture.json'
        if fixture.exists():raise FileExistsError(f'Immutable replication already exists: {out}')
        fixture.write_text(json.dumps(simulate(seed,a.periods,a.groups,a.holdout,True),indent=2))
        offset=index%len(arms)
        for arm in arms[offset:]+arms[:offset]:
            r=execute(fixture,out,arm,a.exe,seed,a.warmup,a.draws,4,a.timeout,
                require_attestation=a.require_attestation,cpus=a.cpus,reference_script=a.reference_script)
            print(seed,arm,r['status'],r.get('healthy'),flush=True)
if __name__=='__main__':main()
