"""Literal engineering route with four concurrent isolated reference compiles."""
import argparse,concurrent.futures,hashlib,json,os,subprocess,time
from pathlib import Path
from batch import load_worker,safe
from evidence_io import exclusive
from inventory_sdk import inventory
from resource_monitor import execute

def common_equal(left,right):
    return left['products']==right['products'] and left['selected_hashes']==right['selected_hashes']

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--out',required=True);a=p.parse_args();manifest=Path(a.manifest).absolute();raw=json.loads(manifest.read_bytes());worker=load_worker(raw['worker_path'],raw['sources'][raw['worker_path']]);spec=worker.admit(manifest,expected_status='development_authorized')
    root=Path(a.out);root.mkdir(exist_ok=False);here=Path(__file__).resolve().parent;start=time.monotonic();deadline=start+570
    before=inventory(spec['sdk_build']['root']);exclusive(root/'SDK-BEFORE.json',before)
    if before['selected_hashes']!=spec['sdk_build']['selected_hashes'] or before['products']!=spec['sdk_build']['products']:raise ValueError('Shared compiler products changed before literal replay')
    with (root/'fixtures.log').open('xb') as log:
        end=time.monotonic()+45
        for folder in (here,Path(spec['worker_path']).parent):
            env=dict(os.environ,OWALNUTS_E62_ROOT=spec['e62_root'])
            subprocess.run([spec['python'],'-m','unittest','discover','-s',str(folder),'-p','test_*.py','-v'],stdout=log,stderr=subprocess.STDOUT,timeout=max(.01,end-time.monotonic()),check=True,env=env)
    jobs=[dict(phase=p,slot=i,status='not_started') for p,n in (('native',1),('baselines',1),('reference',4),('tails',1),('report',1)) for i in range(n)];unsafe=False;sdk_unchanged=None
    def one(phase,slot,cap,affinity):
        owned=root/'monitor'/f'{phase}-{slot}';owned.mkdir(parents=True);cap=min(cap,deadline-time.monotonic()-5)
        if cap<=0:return dict(phase=phase,slot=slot,status='not_started',reason='fixed_readiness_deadline')
        cmd=['taskset','-c',affinity,spec['python'],spec['readiness_path'],phase,'--manifest',str(manifest),'--out',str(root/'work')]
        if phase=='reference':cmd+=['--slot',str(slot)]
        rss=spec['bounds']['reference_worker_rss_bytes'] if phase=='reference' else spec['bounds']['native_worker_rss_bytes']
        result=execute(cmd,Path(spec['readiness_path']).parent,cap,owned,rss,spec['bounds']['output_bytes'],owned/'worker.log',output_scan_interval=2)
        result.update(phase=phase,slot=slot,affinity=affinity);exclusive(owned/'MONITOR.json',result);return result
    for phase,cap in (('native',180),('baselines',60),('reference',180),('tails',90),('report',30)):
        if unsafe:break
        exclusive(root/f'PHASE-{phase}.json',dict(phase=phase,elapsed_seconds=time.monotonic()-start))
        if phase=='reference':
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:current=list(pool.map(lambda i:one(phase,i,cap,f'{4*i}-{4*i+3}'),range(4)))
            after=inventory(spec['sdk_build']['root']);exclusive(root/'SDK-AFTER-REFERENCES.json',after)
            sdk_unchanged=common_equal(before,after)
            if not sdk_unchanged:unsafe=True
        else:current=[one(phase,0,cap,'0-3' if phase=='native' else '0')]
        for item in current:next(j for j in jobs if (j['phase'],j['slot'])==(item['phase'],item['slot'])).update(item)
        if not all(j.get('status')=='exited' and j.get('exit_code')==0 and safe(j) for j in current):unsafe=True
    worker.admit(manifest,expected_status='development_authorized');complete=False;error=None
    try:
        terminal=json.loads((root/'work/readiness-final.json').read_bytes())
        expected=dict(status='complete',native=32,references=4,reference_shape=[4,4000,4],candidate_tail_draws=1600,reference_tail_draws=16000,calendar_accounting=True)
        if any(terminal.get(k)!=v for k,v in expected.items()):raise ValueError('Literal final evidence incomplete')
        copies=[];compiler_sources=[]
        for i in range(4):
            reference=json.loads((root/'work'/f'reference-{i:02d}-final.json').read_bytes())
            if reference.get('status')!='complete' or reference.get('reference_shape')!=[4,4000,4] or not reference.get('compiler_captures'):raise ValueError('Full literal reference provenance incomplete')
            for capture in reference['compiler_captures']:
                copy=Path(capture['copy_path']).resolve();source=Path(capture['source_path']).resolve()
                if not copy.is_relative_to(root.resolve()) or not source.is_relative_to(root.resolve()) or not copy.is_file() or copy.is_symlink() or hashlib.sha256(copy.read_bytes()).hexdigest()!=capture['sha256']:raise ValueError('Captured compiler library identity or containment failure')
                copies.append(str(copy));compiler_sources.append(str(source))
        if len(set(copies))!=len(copies) or len(set(compiler_sources))!=len(compiler_sources):raise ValueError('Reference compiler workspaces aliased')
        complete=not unsafe and all(j.get('status')=='exited' and j.get('exit_code')==0 and safe(j) for j in jobs)
    except Exception as exc:error=repr(exc)
    exclusive(root/'READINESS-FINAL.json',dict(jobs=jobs,planned_jobs=8,complete=complete,error=error,shared_sdk_products_unchanged=sdk_unchanged,source_runtime_postcheck=True,elapsed_seconds=time.monotonic()-start,market_inputs_used=False))
    return 0 if complete else 1
if __name__=='__main__':raise SystemExit(main())
