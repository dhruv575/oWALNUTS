import copy,json
from pathlib import Path
import pytest
import aggregate as a
def cohort():
 origins=[100+i*1_800_000_000_000 for i in range(95)];plan={'schema':'receipt-live-sv-schedule-v1','origins_ns':origins};events=[];scores=[]
 for i,o in enumerate(origins):
  events.append(dict(origin_receipt_ns=o,status='not_issued',issuance_sha256=f'{i:064x}'))
  scores.append(dict(schema='delayed-live-sv-score-v1',origin_receipt_ns=o,issuance_status='not_issued',issuance_sha256=f'{i:064x}',status='not_issued',scored=False,provisional=False,final_reconciliation_required=False))
 return plan,events,scores
def scored():return dict(status='scored',scored=True,observed_return=0.,interval=[-.1,.1],nominal_coverage=.9,width=.2,covered=True,interval_score=.2)
def test_zero_success_denominator_and_null_stats():
 p,e,s=cohort();r=a.summarize(p,e,s);assert r['summary']['intended']==95 and r['summary']['scored_fraction']==0 and r['summary']['coverage_given_scored'] is None and r['summary']['mean_interval_score'] is None
def test_mixed_outcomes_all95_retained():
 p,e,s=cohort();e[0]['status']='issued';s[0].update(issuance_status='issued',**scored());e[1]['status']='issued';s[1].update(issuance_status='issued',status='outcome_unavailable');e[2]['status']='issued';s[2].update(issuance_status='issued',status='invalidated_receipt_coverage')
 r=a.summarize(p,e,s);assert r['summary']['issued']==3 and r['summary']['usable']==2 and r['summary']['scored']==1 and r['summary']['usable_and_covering_fraction']==1/95 and len(r['outcomes'])==95
@pytest.mark.parametrize('kind',['missing','duplicate','provisional','hash','origin','arithmetic'])
def test_invalid_or_incomplete_rejected(kind):
 p,e,s=cohort()
 if kind=='missing':s.pop()
 if kind=='duplicate':s[-1]=copy.deepcopy(s[0])
 if kind=='provisional':s[0]['provisional']=True
 if kind=='hash':s[0]['issuance_sha256']='wrong'
 if kind=='origin':s[0]['origin_receipt_ns']=9
 if kind=='arithmetic':e[0]['status']='issued';s[0].update(issuance_status='issued',**scored());s[0]['interval_score']=99.
 with pytest.raises(ValueError):a.summarize(p,e,s)
def test_optional_paired_baseline_same_label_only():
 p,e,s=cohort();e[0]['status']='issued';s[0].update(issuance_status='issued',**scored());base={'schema':'issued-market-interval-score/v1','origin_receipt_ns':p['origins_ns'][0],'outcomes':[dict(model=name,**scored()) for name in a.BASELINES]}
 r=a.summarize(p,e,s,[base]);assert all(v['common_scored']==1 for v in r['baseline_comparisons'].values())
 base['outcomes'][0]['observed_return']=.01
 with pytest.raises(ValueError,match='return'):a.summarize(p,e,s,[base])
def test_file_identity_and_mutation(tmp_path,monkeypatch):
 p,e,s=cohort();pp=tmp_path/'plan.json';pp.write_text(json.dumps(p));scorepaths=[]
 for i,(ev,r) in enumerate(zip(e,s)):
  issue=tmp_path/f'issued{i}.json';issue.write_text(json.dumps({'origin_receipt_ns':ev['origin_receipt_ns'],'status':'not_issued'}));h=a.hashfile(issue);ev.update(path=str(issue),issuance_sha256=h);r.update(issuance_sha256=h,input_and_source_sha256={str(issue):h});sp=tmp_path/f'score{i}.json';sp.write_text(json.dumps(r));scorepaths.append(sp)
 ep=tmp_path/'events.jsonl';ep.write_text(''.join(json.dumps(v)+'\n' for v in e));r=a.aggregate(pp,ep,scorepaths);assert r['summary']['intended']==95
 original=a.summarize
 def mutate(*args,**kwargs):
  scorepaths[0].write_text('{}');return original(*args,**kwargs)
 monkeypatch.setattr(a,'summarize',mutate)
 with pytest.raises(ValueError,match='changed'):a.aggregate(pp,ep,scorepaths)
@pytest.mark.parametrize('missing',[False,True])
def test_changed_transitive_lineage_retains_all_origins(tmp_path,missing):
 p,e,s=cohort();upstream=tmp_path/'old-source.py';upstream.write_text('before');old=a.hashfile(upstream)
 p['source_sha256']={str(upstream):old};pp=tmp_path/'plan.json';pp.write_text(json.dumps(p));paths=[]
 for i,(ev,r) in enumerate(zip(e,s)):
  issue=tmp_path/f'issued{i}.json';issue.write_text(json.dumps({'origin_receipt_ns':ev['origin_receipt_ns'],'status':'not_issued'}));h=a.hashfile(issue);ev.update(path=str(issue),issuance_sha256=h);r.update(issuance_sha256=h,input_and_source_sha256={str(issue):h,str(upstream):old})
  if i==0:r.update(status='invalid_provenance',error='Source changed detected by scorer')
  sp=tmp_path/f'score{i}.json';sp.write_text(json.dumps(r));paths.append(sp)
 ep=tmp_path/'events.jsonl';ep.write_text(''.join(json.dumps(v)+'\n' for v in e))
 if missing:upstream.unlink()
 else:upstream.write_text('after')
 result=a.aggregate(pp,ep,paths);assert result['summary']['intended']==95 and result['summary']['usable']==0 and result['status_counts']['invalid_provenance']==95
 assert result['outcomes'][0]['original_score_status']=='invalid_provenance' and result['outcomes'][1]['original_score_status']=='not_issued'
 # Event issuance is mandatory identity, even when upstream validation fails.
 Path(e[0]['path']).write_text('{}')
 with pytest.raises(ValueError,match='Bound input'):a.aggregate(pp,ep,paths)
@pytest.mark.parametrize('which',['event','score'])
def test_strict_integer_origins(which):
 p,e,s=cohort();(e if which=='event' else s)[0]['origin_receipt_ns']=float(p['origins_ns'][0])
 with pytest.raises(ValueError,match='integer'):a.summarize(p,e,s)
