"""Archived reconstruction of inline acquisition audit; read-only verifier.
No network. Reproduces committed checks and compares original without overwrite.
Scope: frozen week/thresholds, finite public feed completeness only.
"""
import pathlib,json,hashlib,zipfile,bisect,collections,argparse

def verify(p):
 p=pathlib.Path(p);load=lambda f:json.loads(pathlib.Path(f).read_text());sha=lambda f:hashlib.sha256(pathlib.Path(f).read_bytes()).hexdigest();ep=p.parents[1]/'DERIBIT_ACTIVITY_EXECUTION_V1.json';plan=load(ep);s=load(p/'summary.json');pr=load(p/'protocol.json');ranking=load(p/'activity-ranking.json');hw=load(plan['hardware_record']);checks={}
 checks['execution_pin']=sha(ep)=='0bcf7e56db0595ddde1a4e66263bf4607860bb4c20c49914562c3b830bfeadfb'
 checks['frozen_sources']=all(sha(k)==v for k,v in plan['source_bindings'].items())
 checks['protocol']=hashlib.sha256(json.dumps(pr,sort_keys=True,separators=(',',':')).encode()).hexdigest()==s['protocol_sha256']==plan['protocol_canonical_sha256']
 checks['failure_contained']=hw['returncode']==2 and hw['status']=='worker-failed' and hw['job_active_processes_after_cleanup']==0 and hw['realized_cpus']==[0] and hw['command']==plan['command'][plan['command'].index('--')+1:]
 checks['incomplete_not_selected']=s['status']=='incomplete' and not (p/'selection.json').exists() and s['selected']==[]
 with zipfile.ZipFile(p/'source-snapshots.zip') as z:checks['exact_source_archive']=all(hashlib.sha256(z.read(k)).hexdigest()==v for k,v in s['source_dependencies_sha256'].items())
 requests=sorted(p.glob('*.request.json'));leaves=[];ranges={};byid={};total=0;inventory={}
 for ix,fp in enumerate(requests,1):
  r=load(fp);raw=fp.with_name(fp.name.replace('.request.json','.response'));b=raw.read_bytes();total+=len(b);inventory[fp.name]=sha(fp);inventory[raw.name]=sha(raw)
  assert r['response_sha256']==sha(raw) and r['response_bytes']==len(b) and r['cumulative_requests']==ix and r['cumulative_raw_bytes']==total and r['http_status']==200 and r['error'] is None
  response=json.loads(b)['result'];params=r['params'];lo,hi=params['start_timestamp'],params['end_timestamp'];ranges[(lo,hi)]=response['has_more'];assert r['method']=='public/get_last_trades_by_currency_and_time'
  for t in response['trades']:assert lo<=t['timestamp']<=hi
  if not response['has_more']:
   leaves.append((lo,hi))
   for t in response['trades']:
    key=t['trade_id'];assert key not in byid or byid[key]==t;byid[key]=t
 checks['request_raw_inventory']=len(requests)==s['requests']==31 and total==s['raw_response_bytes']==6175791
 start=ranking['selection_start_ms'];end=ranking['selection_end_ms_exclusive'];reach=start-1
 for lo,hi in sorted(leaves):assert lo<=reach+1;reach=max(reach,hi)
 checks['complete_discovery']=reach==end-1 and min(lo for lo,hi in leaves)==start and all((lo==hi or ((lo,(lo+hi)//2) in ranges and ((lo+hi)//2,hi) in ranges) or (lo,lo) in ranges and (hi,hi) in ranges) for (lo,hi),more in ranges.items() if more)
 groups={}
 for t in byid.values():
  if not any(t.get(k) is not None for k in pr['exclude_flags']):groups.setdefault(t['instrument_name'],[]).append(t['timestamp'])
 metrics={};policy=ranking['policy']
 for name,times in groups.items():
  times.sort();fresh=active=0
  for cutoff in range(start+1800000,end,1800000):
   last=bisect.bisect_right(times,cutoff);fresh+=bool(last and cutoff-times[last-1]<=1800000);active+=last>bisect.bisect_right(times,cutoff-900000)
  reasons=[k for val,k in [(len(times),'minimum_trades'),(fresh,'minimum_fresh_anchor_bins'),(active,'minimum_active_feature_bins')] if val<policy[k]];metrics[name]=dict(eligible_trades=len(times),fresh_anchor_bins=fresh,active_feature_bins=active,rejection_reasons=reasons)
 checks['ranking_recomputed']=metrics==ranking['metrics'] and ranking['ranked_candidates']==[]
 checks['pre_request_snapshot']=(p/'source-snapshots.zip').stat().st_mtime_ns<requests[0].stat().st_mtime_ns
 original=load(p/'independent-audit.json')
 return dict(integrity_pass=all(checks.values()),checks=checks,original_checks_identical=checks==original['checks'],original_inventory_identical=inventory==original['artifact_sha256'],original_counts_identical=len(leaves)==original['complete_leaf_windows'] and len(byid)==original['unique_discovery_trades'] and len(metrics)==original['eligible_instruments'],scope='Only this fixed historical week and frozen activity thresholds; completeness is relative to archived API feed pagination, not independent exchange-wide completeness. File-time archive-before-request check is local evidence; archived collector source establishes ordering.',auditor_sha256=sha(__file__),original_audit_sha256=sha(p/'independent-audit.json'))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('directory');a.add_argument('--out',required=True);v=a.parse_args();r=verify(v.directory)
 with pathlib.Path(v.out).open('x') as f:json.dump(r,f,indent=2)
 print(r['integrity_pass'],r['original_checks_identical'],r['original_inventory_identical'],r['original_counts_identical'])
