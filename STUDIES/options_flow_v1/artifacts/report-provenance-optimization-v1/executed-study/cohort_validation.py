"""Versioned shared-binding transaction seam. No legacy adapter monkeypatching."""
import copy,hashlib,os
from pathlib import Path
POLICY='cohort-content-prepost-v1'

def digest(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for block in iter(lambda:f.read(1048576),b''):h.update(block)
 return h.hexdigest()

class SharedValidation:
 def __init__(self,binding_sets,inventory,expected_inventory,hash_file=digest):
  self.bindings={};self.inventory=inventory;self.expected_inventory=frozenset(os.path.normcase(str(Path(p).resolve())) for p in expected_inventory);self.hash_file=hash_file;self.state='new';self.policy=POLICY
  self.conflict=None
  for bindings in binding_sets:
   for path,expected in bindings.items():
    key=os.path.normcase(str(Path(path).resolve()))
    if key in self.bindings and self.bindings[key][1]!=expected:self.conflict='Conflicting shared binding: '+path
    self.bindings[key]=(str(Path(path).resolve()),expected)
 def _check(self):
  if not self.bindings or not self.expected_inventory:raise ValueError('Nonempty frozen shared bindings and inventory required')
  if not self.expected_inventory.issubset(self.bindings):raise ValueError('Expected source inventory must be hash-bound')
  if self.conflict:raise ValueError(self.conflict)
  for path,expected in self.bindings.values():
   if self.hash_file(path)!=expected:raise ValueError('Shared content drift: '+path)
 def begin(self):
  if self.state!='new':raise RuntimeError('Context is single-use')
  self.state='checking';self.initial_inventory=frozenset(os.path.normcase(str(Path(p).resolve())) for p in self.inventory())
  if self.initial_inventory!=self.expected_inventory:raise ValueError('Initial source inventory differs from frozen expected inventory')
  self._check();self.state='active'
 def require(self,bindings):
  """Adapter seam: replaces shared loops only under explicit policy admission.

  Per-cell artifact/content/identity validation remains the adapter's responsibility.
  This does not assert unchanged content at this instant; final cohort check is required.
  """
  if self.state!='active':raise RuntimeError('No active validation transaction')
  for path,expected in bindings.items():
   entry=self.bindings.get(os.path.normcase(str(Path(path).resolve())))
   if entry is None or entry[1]!=expected:raise ValueError('Unadmitted shared binding')
 def finish(self):
  if self.state!='active':raise RuntimeError('No active transaction')
  self.state='checking'
  self._check()
  if frozenset(os.path.normcase(str(Path(p).resolve())) for p in self.inventory())!=self.initial_inventory:raise ValueError('Shared source inventory membership changed')
  self.state='verified'

def fallback_record(cell):
 row=copy.deepcopy(cell.get('record_template',{}))
 row.update(id=cell['id'],provenance_valid=False,usable=False,cost=copy.deepcopy(cell.get('known_cost',{})),failure_evidence=copy.deepcopy(cell.get('failure_evidence',{})))
 return row

def normalize_cohort(cells,binding_sets,normalize_cell,inventory,expected_inventory,hash_file=digest):
 """Return authoritative results only after postcheck; no publication callback.

 normalize_cell(cell,context) must return existing adapter record; costs and local
 failure classifications are preserved. It must keep all local validation checks.
 """
 cells=list(cells);rows=[];context=None;shared_error=None
 try:
  context=SharedValidation(binding_sets,inventory,expected_inventory,hash_file)
  context.begin()
 except Exception as exc:shared_error=f'{type(exc).__name__}: {exc}'
 for cell in cells:
  if shared_error is not None:
   rows.append(fallback_record(cell))
   continue
  try:
   row=normalize_cell(cell,context)
   if not isinstance(row,dict) or row.get('id')!=cell['id']:raise ValueError('Normalizer returned wrong record identity/type')
   rows.append(copy.deepcopy(row))
  except Exception as exc:
   row=fallback_record(cell);row['local_normalization_error']=f'{type(exc).__name__}: {exc}';rows.append(row)
 if shared_error is None:
  try:context.finish()
  except Exception as exc:shared_error=f'{type(exc).__name__}: {exc}'
 if shared_error:
  for row in rows:
   row.update(provenance_valid=False,usable=False,shared_provenance_failure=shared_error)
 for row in rows:
  pending=row.pop('shared_validation_pending_flags',None)
  if shared_error is None and pending is not None:row.update(pending)
  row.pop('shared_validation_provisional',None)
 return dict(policy=POLICY,expected=len(cells),records=rows,shared_validation_passed=shared_error is None,shared_error=shared_error,qualified=False)
