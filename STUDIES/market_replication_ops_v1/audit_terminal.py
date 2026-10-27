"""Independent terminal operational audit; no sampling, scoring or resampling."""
import argparse,hashlib,json,datetime
from pathlib import Path,PurePosixPath

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
def audit(root,pending,reservations):
 root=Path(root).resolve();work=root/'campaign01/batch';manifest=read(root/'PRODUCTION-AUTHORIZED.json');before=read(pending);before['status']='frozen_scoring_authorized';checks={};files={}
 def check(name,condition):
  checks[name]=bool(condition)
  if not condition:raise ValueError(name)
 def tracked(p):files[str(p.relative_to(root))]=sha(p);return read(p)
 check('authorization_status_only',before==manifest);check('authorized_sha256',sha(root/'PRODUCTION-AUTHORIZED.json')=='1a6c25d68202d1172569dbcb922b5a5d7a6e408615b1e4b3db5c4ba1dd7e340d');check('readiness_authorized_sha256',sha(root/'READINESS-AUTHORIZED.json')=='f1e0f18f4df7d6fde880d11a2875308940f4a63eeca12b32d5e5dd2b0e992714')
 outer=tracked(root/'campaign01/BATCH-SUPERVISION.json');batch=tracked(work/'BATCH-FINAL.json');start=tracked(work/'BATCH-START.json');seal=tracked(root/'ARCHIVE-SEAL.json');check('archive_seal_links_supervision',seal['supervision_sha256']==sha(root/'campaign01/BATCH-SUPERVISION.json'))
 check('outer_success_and_drain',outer['status']=='exited' and outer['exit_code']==0 and outer['evidence_complete'] and outer['execution_complete'] and outer['group_drained'] and outer['remaining_owned_pids']==[] and outer['manifest_unchanged'] and not outer.get('orphaned_children_after_leader_exit'))
 b=manifest['bounds'];check('outer_resource_limits',outer['cap_seconds']==3720 and outer['elapsed_seconds']<=3725 and outer['peak_rss']<=b['rss_bytes'] and outer['peak_output_bytes']<=b['output_bytes'] and outer['final_output_bytes']<=b['output_bytes'] and outer['output_scan_interval_seconds']==2)
 months=manifest['months'];expected=[(m['month'],phase,i) for phase,n in [('candidate',1),('baselines',1),('reference',8),('report',1)] for m in months for i in range(n)];jobs=batch['jobs'];check('all_33_job_identities',[(j['month'],j['phase'],j['index']) for j in jobs]==expected);check('planned_before_launch',len(start['jobs'])==33 and all(j['status']=='not_started' for j in start['jobs']));check('batch_complete_flags',batch['job_accounting_complete'] and batch['execution_complete'] and batch['all_launched_groups_drained'] and batch['aggregate_written'] and batch['aggregate_error'] is None)
 timestamps=[];limits=[]
 for j in jobs:
  ident=f"{j['month']}-{j['phase']}-{j['index']:02d}";monitor=tracked(work/('monitor-'+ident+'.json'));check('monitor_matches:'+ident,monitor==j);check('job_exit_drain:'+ident,j['status']=='exited' and j['exit_code']==0 and j['group_drained'] and j['remaining_owned_pids']==[] and not j.get('orphaned_children_after_leader_exit'))
  check('job_resource_limits:'+ident,j['elapsed_seconds']<=j['cap_seconds']+5 and j['peak_rss']<=b['rss_bytes'] and j['final_output_bytes']<=b['output_bytes'] and j['output_scan_interval_seconds']==2)
  record=tracked(work/j['month']/'jobs'/f"{j['phase']}-{j['index']:02d}.json");check('job_manifest_and_postcheck:'+ident,record['manifest_sha256']==sha(root/'PRODUCTION-AUTHORIZED.json') and record['postrun_bindings_held'] and record['status']=='complete');timestamps.append(dict(month=j['month'],phase=j['phase'],index=j['index'],start=record['started_unix'],end=record['ended_unix']))
  expected_affinity={'2026-04':'0-3','2026-05':'4-7','2026-06':'8-11'}[j['month']] if j['phase']=='candidate' else '0-3';check('affinity:'+ident,j['affinity']==expected_affinity);limits.append(dict(job=ident,seconds=j['elapsed_seconds'],cap=j['cap_seconds'],peak_rss=j['peak_rss']))
 for earlier,later in [('candidate','baselines'),('baselines','reference'),('reference','report')]:check('phase_barrier:'+earlier+'_'+later,max(x['end'] for x in timestamps if x['phase']==earlier)<=min(x['start'] for x in timestamps if x['phase']==later))
 for phase in ('baselines','reference','report'):
  ordered=[x for x in timestamps if x['phase']==phase];check('serial_order:'+phase,all(a['end']<=z['start'] for a,z in zip(ordered,ordered[1:])))
 seedrows=read(reservations)['months'];monthly=[]
 for m,s in zip(months,seedrows):
  check('month_seed_equality:'+m['month'],m['seeds']==dict(candidate=dict(initial=s['initial'],warm=s['warm']),references=[s['reference_base']+s['reference_stride']*i for i in range(8)],bootstrap=s['bootstrap']))
  folder=work/m['month'];v=tracked(folder/'terminal-validation.json');owned=tracked(folder/'OPERATIONAL-JOBS.json');check('month_job_accounting:'+m['month'],owned==[j for j in jobs if j['month']==m['month']]);check('month_denominators:'+m['month'],v['planned_origins']==m['origins'] and v['planned_forecasts']==m['origins']*3 and v['planned_references']==8 and v['accounting_complete'] and v['execution_complete'] and v['artifact_integrity']['integrity_ok'])
  ledger=read(folder/'terminal-ledger.json');check('month_ledger_identity:'+m['month'],len(ledger)==m['origins'] and [r['tick'] for r in ledger]==list(range(1,m['origins']+1)));counts={arm:sum(r['arms'][arm]['status']=='ok' for r in ledger) for arm in ('candidate','rolling_t5','ewma_t5')};check('month_score_counts:'+m['month'],counts==v['valid_scores']);refs=read(folder/'terminal-references.json');check('reference_slot_identity:'+m['month'],len(refs)==8 and [r['index'] for r in refs]==list(range(8)) and [r['tick'] for r in refs]==m['reference_ticks']);monthly.append(dict(month=m['month'],origins=m['origins'],valid_scores=counts,references_complete=v['references_complete'],reference_diagnostics_pass=v['reference_diagnostics_pass']))
 inventory=read(root/'source01/BUNDLE-MANIFEST.json')['files']
 for relative,want in inventory.items():check('archived_source:'+relative,sha(root/'source01'/relative)==want)
 acq=manifest['acquisition'];check('acquisition_bars_identity',sha(root/'acquisition/bars.json')==acq['bars_sha256']);check('acquisition_protocol_identity',sha(root/'acquisition/protocol.json')==acq['protocol_sha256']);check('acquisition_terminal_identity',sha(root/'acquisition/terminal.json')==acq['terminal_sha256']);check('acquisition_supervisor_identity',sha(root/'acquisition-supervisor-final.json')==acq['supervisor_final_sha256'])
 aggregate=tracked(work/'aggregate.json');check('aggregate_denominators',aggregate['planned_origins']==4368 and aggregate['planned_forecasts']==13104 and aggregate['planned_references']==24)
 for m in aggregate['months']:check('aggregate_summary_identity:'+m['month'],m['summary_sha256']==sha(work/m['month']/'summary.json'))
 return dict(status='operational_audit_passed',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope='Terminal operational/manifest/seed/resource accounting only; no forecasts, likelihoods, sampler, bootstrap or statistical comparisons recomputed',archive_sha256='da1e3025d746e6b7984fef03c7bf55afeb6963274edba46f697aaac80c993f6d',root=str(root),checks=checks,metadata_sha256=files,monthly=monthly,planned_jobs=33,planned_origins=4368,planned_forecasts=13104,planned_references=24,outer_seconds=outer['elapsed_seconds'],inner_seconds=batch['elapsed_seconds'],peak_rss=outer['peak_rss'],output_bytes=outer['final_output_bytes'],job_resources=limits,limits='Parent independently verified full archive and40648 file hashes. This audit independently checked declared archived source and input bindings plus metadata; external installed binary/SDK checks are recorded runtime admissions, not independently reread after host stop.')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('pending');p.add_argument('reservations');p.add_argument('output');a=p.parse_args();result=audit(a.root,a.pending,a.reservations)
 with Path(a.output).open('x') as f:json.dump(result,f,indent=2);f.write('\n')
 print({k:result[k] for k in ('status','planned_jobs','planned_origins','planned_forecasts','planned_references','outer_seconds','peak_rss','output_bytes','monthly')})
