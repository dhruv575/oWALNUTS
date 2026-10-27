"""Post-run operational metadata audit; no model, scoring, or bootstrap calls."""
import argparse,hashlib,json,math,shutil
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_bytes())

def audit(root,out):
    root=Path(root);out=Path(out);out.mkdir(parents=True,exist_ok=False);batch=root/'campaign01/batch'
    auth=load(root/'PRODUCTION-AUTHORIZED.json');pending=load(root/'PRODUCTION-PENDING.json')
    assert auth['status']=='frozen_authorized'
    assert {k:v for k,v in auth.items() if k!='status'}=={k:v for k,v in pending.items() if k!='status'}
    bounds=auth['bounds'];outer=load(root/'campaign01/BATCH-SUPERVISION.json');final=load(batch/'BATCH-FINAL.json')
    assert outer['status']=='exited' and outer['exit_code']==0 and outer['group_drained'] and outer['remaining_owned_pids']==[]
    assert outer['evidence_complete'] and outer['execution_complete'] and outer['manifest_unchanged']
    assert outer['elapsed_seconds']<=bounds['external_seconds'] and outer['peak_rss']<=bounds['rss_bytes'] and outer['final_output_bytes']<=bounds['output_bytes']
    assert all(final[k] for k in ('job_accounting_complete','execution_complete','all_jobs_successful','all_launched_groups_drained','aggregate_written'))
    assert final['aggregate_error'] is None and final['accounting_error'] is None and final['elapsed_seconds']<=bounds['whole_seconds']
    expected={(p,i) for p in ('candidate','reference') for i in range(12)}|{('report',m['month']) for m in auth['months']}
    assert {(j['phase'],j.get('shard',j.get('month'))) for j in final['jobs']}==expected and len(final['jobs'])==27
    rows=[]
    for job in final['jobs']:
        assert job['status']=='exited' and job['exit_code']==0 and job['group_drained'] and job['remaining_owned_pids']==[] and not job.get('orphaned_children_after_leader_exit')
        assert job['peak_rss']<=bounds['worker_rss_bytes'] and job['elapsed_seconds']<=job['cap_seconds']
        row={k:job[k] for k in ('phase','elapsed_seconds','peak_rss','affinity')};row['identity']=job.get('shard',job.get('month'))
        if job['phase']!='report':
            assert job['affinity']==str(job['shard'])
            state=load(batch/'jobs'/f"{job['phase']}-{job['shard']:02d}.json")
            count=364 if job['phase']=='candidate' else 2
            assert state['status']=='complete' and state['planned']==state['completed']==count
            row.update(planned=count,completed=count,startup_seconds=state['startup_seconds'])
        rows.append(row)
    accounting=final['accounting']
    assert accounting['accounting_complete'] and accounting['artifact_integrity']['integrity_ok'] and accounting['artifact_integrity']['errors']==[]
    assert (accounting['planned_candidate_origins'],accounting['planned_reference_origins'],accounting['planned_arm_origins'])==(4368,24,13104)
    source_manifest=load(root/'source02/BUNDLE-MANIFEST.json')
    for name,want in source_manifest['files'].items():assert sha(root/'source02'/name)==want,name
    utilization=[json.loads(line) for line in (root/'campaign01/utilization.jsonl').read_text().splitlines()]
    phase_stats={}
    for phase in ('candidate','reference','report'):
        samples=[r for r in utilization if r['phase']==phase and r['interval_seconds'] is not None]
        if not samples:phase_stats[phase]=dict(samples=0);continue
        assert all(math.isfinite(r['normalized_reserved_cpu_fraction']) and r['normalized_reserved_cpu_fraction']>=0 for r in samples)
        seconds=sum(r['interval_seconds'] for r in samples);cpu=sum(r['observed_cpu_delta_seconds'] for r in samples)
        phase_stats[phase]=dict(samples=len(samples),sampled_interval_seconds=seconds,observed_cpu_seconds=cpu,weighted_average_reserved_cpu_fraction=cpu/(12*seconds),max_reserved_cpu_fraction=max(r['normalized_reserved_cpu_fraction'] for r in samples))
    names=['PRODUCTION-AUTHORIZED.json','PRODUCTION-PENDING.json','ARCHIVE-SEAL.json','source02/BUNDLE-MANIFEST.json','campaign01/LAUNCH.json','campaign01/BATCH-SUPERVISION.json','campaign01/utilization.jsonl']
    names += ['campaign01/batch/'+n for n in ('BATCH-FINAL.json','BATCH-START.json','OPERATIONAL-JOBS.json','PHASE-candidate.json','PHASE-reference.json','PHASE-report.json','evidence-validation.json')]
    names += [p.relative_to(root).as_posix() for p in batch.glob('monitor-*.json')]
    names += [p.relative_to(root).as_posix() for p in (batch/'jobs').glob('*.json')]
    index={name.removeprefix('./'):digest for digest,name in (line.split('  ',1) for line in (root/'ARTIFACTS.sha256').read_text().splitlines())}
    copied={}
    for name in names:
        want=sha(root/name)
        if name!='ARCHIVE-SEAL.json':assert index[name]==want,name
        dest=out/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,dest);assert sha(dest)==want;copied[name]=want
    report=dict(status='verified',scope='Metadata-only operational audit, no scientific outcome recomputation',authorized_manifest_sha256=sha(root/'PRODUCTION-AUTHORIZED.json'),status_only_authorization=True,source_files_verified=len(source_manifest['files']),copied_metadata_files=len(copied),planned_jobs=27,planned_candidate_origins=4368,planned_reference_origins=24,planned_arm_origins=13104,outer_seconds=outer['elapsed_seconds'],outer_peak_rss=outer['peak_rss'],outer_output_bytes=outer['final_output_bytes'],workers=rows,utilization=phase_stats,utilization_limitations='Sampled live owned-process deltas include batch orchestration and nested process monitors, not only the twelve arithmetic workers. Denominator is twelve reserved cores; values may exceed 100%. First sightings and exited processes between samples omit CPU. Intervals crossing phase boundaries are attributed to the phase at their endpoint; these are descriptive utilization estimates, not exact kernel CPU accounting.',aws_lifecycle_actions=False,qualification=None)
    (out/'AUDIT.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'COPIED-CHECKSUMS.sha256').write_text(''.join(v+'  '+k+'\n' for k,v in sorted(copied.items())))
    print(json.dumps({k:v for k,v in report.items() if k!='workers'}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('out');a=p.parse_args();audit(a.root,a.out)
