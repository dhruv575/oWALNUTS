import os
from pathlib import Path
import pytest
from cohort_validation import digest,normalize_cohort,SharedValidation

def setup(tmp_path):
 p=tmp_path/'source.py';p.write_text('old');binding={str(p):digest(p)}
 cells=[dict(id=str(i),known_cost={'seconds':i+1}) for i in range(3)]
 return p,binding,cells

def test_two_hashes_not_percell_and_no_cache_between_calls(tmp_path):
 p,b,cells=setup(tmp_path);calls=[]
 def hashed(path):calls.append(path);return digest(path)
 def adapter(cell,context):context.require(b);return dict(id=cell['id'],usable=True,provenance_valid=True,cost=cell['known_cost'])
 for _ in range(2):
  r=normalize_cohort(cells,[b,b],adapter,lambda:[str(p)],[str(p)],hashed);assert r['shared_validation_passed'] and all(x['usable'] for x in r['records'])
 assert len(calls)==4

def test_same_size_restored_timestamp_drift_invalidates_early_and_late(tmp_path):
 p,b,cells=setup(tmp_path);stat=p.stat()
 def adapter(cell,ctx):
  ctx.require(b)
  if cell['id']=='1':p.write_text('new');os.utime(p,ns=(stat.st_atime_ns,stat.st_mtime_ns))
  return dict(id=cell['id'],usable=True,provenance_valid=True,cost=cell['known_cost'],failure_evidence={'original':'retained'})
 r=normalize_cohort(cells,[b],adapter,lambda:[str(p)],[str(p)])
 assert not r['shared_validation_passed'] and len(r['records'])==3
 assert all(not row['usable'] and row['failure_evidence']=={'original':'retained'} and row['cost']['seconds']>0 for row in r['records'])

@pytest.mark.parametrize('mode',['conflict','preexisting'])
def test_failed_admission_retains_denominator_costs_and_does_not_call_adapter(tmp_path,mode):
 p,b,cells=setup(tmp_path);bindings=[b]
 if mode=='conflict':bindings.append({str(p):'wrong'})
 else:p.write_text('changed')
 r=normalize_cohort(cells,bindings,lambda *a:pytest.fail('Not admitted'),lambda:[str(p)],[str(p)])
 assert len(r['records'])==3 and all(not row['provenance_valid'] for row in r['records'])
 assert [row['cost']['seconds'] for row in r['records']]==[1,2,3]

def test_membership_change_and_local_failure_preserved(tmp_path):
 p,b,cells=setup(tmp_path)
 def adapter(cell,ctx):
  if cell['id']=='0':return dict(id='0',usable=False,provenance_valid=True,failure_evidence={'classification':'budgeted_timeout'},cost={'seconds':1800})
  (tmp_path/'added.py').write_text('new')
  return dict(id=cell['id'],usable=True,provenance_valid=True)
 r=normalize_cohort(cells,[b],adapter,lambda:[str(f) for f in tmp_path.glob('*.py')],[str(p)])
 assert not r['shared_validation_passed'] and r['records'][0]['failure_evidence']['classification']=='budgeted_timeout' and r['records'][0]['cost']['seconds']==1800

def test_local_exception_does_not_invalidate_other_rows(tmp_path):
 p,b,cells=setup(tmp_path)
 def adapter(cell,ctx):
  if cell['id']=='1':raise ValueError('bad local artifact')
  return dict(id=cell['id'],usable=True,provenance_valid=True)
 r=normalize_cohort(cells,[b],adapter,lambda:[str(p)],[str(p)])
 assert r['shared_validation_passed'] and [x['usable'] for x in r['records']]==[True,False,True]

def test_context_requires_explicit_active_admission_and_is_single_use(tmp_path):
 p,b,cells=setup(tmp_path);ctx=SharedValidation([b],lambda:[str(p)],[str(p)])
 with pytest.raises(RuntimeError):ctx.require(b)
 ctx.begin()
 with pytest.raises(ValueError):ctx.require({str(p):'other'})
 ctx.finish()
 with pytest.raises(RuntimeError):ctx.require(b)
 with pytest.raises(RuntimeError):ctx.begin()


def test_malformed_binding_constructor_preserves_all_rows_and_costs(tmp_path):
 p,b,cells=setup(tmp_path);cells[0]['failure_evidence']={'classification':'original_timeout'}
 r=normalize_cohort(cells,[{None:'bad'}],lambda *a:pytest.fail('Not admitted'),lambda:[str(p)],[str(p)])
 assert r['expected']==3 and len(r['records'])==3 and not r['shared_validation_passed']
 assert r['records'][0]['failure_evidence']==cells[0]['failure_evidence']
 assert [x['cost']['seconds'] for x in r['records']]==[1,2,3]

def test_preexisting_added_source_rejected_against_frozen_inventory(tmp_path):
 p,b,cells=setup(tmp_path);added=tmp_path/'added.py';added.write_text('new')
 r=normalize_cohort(cells,[b],lambda *a:pytest.fail('Not admitted'),lambda:[str(p),str(added)],[str(p)])
 assert not r['shared_validation_passed'] and 'frozen expected' in r['shared_error']

def test_local_exception_retains_original_failure_evidence(tmp_path):
 p,b,cells=setup(tmp_path);cells[0]['failure_evidence']={'classification':'worker_exception'}
 def adapter(*a):raise OSError('read failure')
 r=normalize_cohort(cells,[b],adapter,lambda:[str(p)],[str(p)])
 assert r['records'][0]['failure_evidence']==cells[0]['failure_evidence'] and r['records'][0]['cost']==cells[0]['known_cost']


@pytest.mark.parametrize('returned',[None,[],{'id':'wrong','usable':True}])
def test_bad_adapter_return_is_retained_local_failure(tmp_path,returned):
 p,b,cells=setup(tmp_path)
 r=normalize_cohort(cells,[b],lambda *a:returned,lambda:[str(p)],[str(p)])
 assert [x['id'] for x in r['records']]==['0','1','2'] and all(not x['usable'] for x in r['records'])
 assert [x['cost']['seconds'] for x in r['records']]==[1,2,3]

def test_empty_shared_policy_rejected(tmp_path):
 p,b,cells=setup(tmp_path)
 for bindings,expected in [([], [str(p)]),([b],[])]:
  r=normalize_cohort(cells,bindings,lambda *a:pytest.fail('Not admitted'),lambda:expected,expected)
  assert not r['shared_validation_passed'] and len(r['records'])==3


def test_expected_inventory_requires_content_bindings(tmp_path):
 p,b,cells=setup(tmp_path);extra=tmp_path/'unbound.py';extra.write_text('unbound')
 r=normalize_cohort(cells,[b],lambda *a:pytest.fail('Not admitted'),lambda:[str(p),str(extra)],[str(p),str(extra)])
 assert not r['shared_validation_passed'] and 'hash-bound' in r['shared_error']
