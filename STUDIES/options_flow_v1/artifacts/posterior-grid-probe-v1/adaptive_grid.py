"""Deterministic shared-grid prototype; estimated errors, never formal envelopes."""
import math
ORDERS=(16,32,64,128)

def build(mixtures,*,initial=(-4.,4.),probabilities=(.05,.95),max_queries=128,max_rounds=32,absolute_width=.002,cdf_tolerance=1e-8,scenarios=None,frozen_weights=None):
 import numpy as np
 if not probabilities or any(type(p) not in (int,float) or not math.isfinite(p) or not 0<p<1 for p in probabilities) or any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in [absolute_width,cdf_tolerance]):raise ValueError('Invalid probabilities/tolerances')
 if not mixtures or len(initial)!=2 or not all(math.isfinite(x) for x in initial) or initial[0]>=initial[1] or type(max_queries)!=int or max_queries<2 or type(max_rounds)!=int or max_rounds<1 or absolute_width<=0 or cdf_tolerance<=0:raise ValueError('Invalid grid budget/tolerances')
 ids=list(mixtures);weights=scenarios or [{k:1 for k in ids}]+[{k:1} for k in ids]
 if any(not w or set(w)-set(ids) or any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in w.values()) or sum(w.values())<=0 for w in weights):raise ValueError('Invalid mixture scenario')
 cache={k:{} for k in ids};pending=list(initial);reason='round_cap';checks=[]
 for round_no in range(max_rounds):
  existing=set(cache[ids[0]]);pending=sorted(set(pending)-existing)
  if len(existing)+len(pending)>max_queries:reason='query_cap';break
  for k,mix in mixtures.items():
   values=np.asarray([mix.cdf(pending,order=o) for o in ORDERS],float)
   if values.shape!=(4,len(pending)) or not np.isfinite(values).all() or (values<0).any() or (values>1).any():raise ValueError('Invalid CDF evaluation')
   for j,x in enumerate(pending):cache[k][x]=values[:,j].tolist()
  grid=sorted(cache[ids[0]]);errors={k:max(max(abs(v[3]-v[2]),abs(v[2]-v[1])) for v in rows.values()) for k,rows in cache.items()}
  if any(any(cache[k][b][-1]<cache[k][a][-1] for a,b in zip(grid,grid[1:])) for k in ids):raise ValueError('Nonmonotone CDF')
  checks=[];next_points=set();quad_ok=all(e<=cdf_tolerance for e in errors.values())
  for si,w in enumerate(weights):
   total=sum(w.values());cdf=[sum(w.get(k,0)*cache[k][x][-1] for k in ids)/total for x in grid];error=sum(w.get(k,0)*errors[k] for k in ids)/total
   for prob in probabilities:
    low=[j for j,v in enumerate(cdf) if v+error<prob];high=[j for j,v in enumerate(cdf) if v-error>=prob]
    if not low or not high:
     span=grid[-1]-grid[0];next_points.add(grid[0]-span if not low else grid[-1]+span);checks.append(dict(scenario=si,probability=prob,bracket=None,resolved=False));continue
    lo,hi=grid[max(low)],grid[min(high)];ok=hi-lo<=absolute_width and quad_ok
    checks.append(dict(scenario=si,probability=prob,bracket=[lo,hi],estimated_inversion_half_width=(hi-lo)/2,cdf_error_estimate=error,resolved=ok))
    if hi-lo>absolute_width:next_points.add((lo+hi)/2)
  # Conservative union of every possible convex-mixture quantile window.
  # For any mixture straddling p in a gap these min/max conditions are necessary.
  # Refining every qualifying gap therefore covers arbitrary weights, conditional
  # on the declared estimated CDF errors (not certified envelopes).
  union_gaps=[]
  for left,right in zip(grid,grid[1:]):
   if any(min(cache[k][left][-1]-errors[k] for k in ids)<prob and max(cache[k][right][-1]+errors[k] for k in ids)>=prob for prob in probabilities):
    if right-left>absolute_width:union_gaps.append([left,right]);next_points.add((left+right)/2)
  weighted=None
  if frozen_weights is not None:
   current={k:dict(grid=grid,cdf=[cache[k][x][-1] for x in grid],numerical_cdf_error_estimate=errors[k]) for k in ids}
   weighted=weighted_brackets(current,frozen_weights,probabilities=probabilities,absolute_width=absolute_width)
   next_points.update((lo+hi)/2 for lo,hi in weighted['refine_intervals'])
  if all(c['resolved'] for c in checks) and not union_gaps and (weighted is None or weighted['resolved']):reason=None;break
  if weighted is not None and weighted['unbracketed']:
   span=grid[-1]-grid[0];next_points.update([grid[0]-span,grid[-1]+span])
  if not quad_ok:reason='quadrature_unresolved';break
  if not next_points:reason='refinement_stalled';break
  pending=sorted(next_points)
 rows={k:dict(grid=sorted(v),cdf=[v[x][-1] for x in sorted(v)],error_bound_verified=False,numerical_cdf_error_estimate=errors[k],numerical_checks_passed=errors[k]<=cdf_tolerance,numerical_checks_provenance='Full16/32/64/128 ladder, max of final two changes at all queried points; convergence estimate not rigorous bound.') for k,v in cache.items()}
 return dict(frozen_weight_rows=0 if frozen_weights is None else len(frozen_weights),declared_weight_brackets_resolved=bool(reason is None and frozen_weights is not None),status='numerically_resolved_for_declared_scenarios' if reason is None else 'unresolved',reason=reason,queries=len(cache[ids[0]]),orders=list(ORDERS),rows=rows,checks=checks,scenarios=weights,absolute_width=absolute_width,all_weight_vectors_verified=reason is None and all(e==0 for e in errors.values()),all_convex_grid_spacing_verified=reason is None,unseen_weight_numerical_brackets_verified=reason is None and all(e==0 for e in errors.values()),coverage_contract='Conservative grid-spacing coverage for all convex fit/prefix mixtures; total numerical-envelope widths verified only for declared scenarios unless errors are identically zero. Not certified quadrature bounds',qualified=False,scope='Conservative common-grid refinement covers every convex fit/prefix mixture when resolved, conditional on estimated quadrature envelopes. Error estimates are not rigorous bounds.')

def weighted_brackets(rows,weights,*,probabilities=(.05,.95),absolute_width=.002,chunk=512):
 """Evaluate ALL prespecified count rows, without redrawing after refinement."""
 import numpy as np
 ids=list(rows);grid=np.asarray(rows[ids[0]]['grid']);matrix=np.asarray(weights,float)
 if matrix.ndim!=2 or matrix.shape[1]!=len(ids) or not len(matrix) or not np.isfinite(matrix).all() or (matrix<0).any() or (matrix.sum(axis=1)<=0).any():raise ValueError('Invalid frozen weight matrix')
 if any(rows[k]['grid']!=grid.tolist() for k in ids):raise ValueError('Common grid required')
 cdf=np.asarray([rows[k]['cdf'] for k in ids]);error=np.asarray([rows[k]['numerical_cdf_error_estimate'] for k in ids])[:,None]
 lower=np.maximum(0,cdf-error);upper=np.minimum(1,cdf+error);brackets=[];failed=set();unbracketed=False
 for start in range(0,len(matrix),chunk):
  w=matrix[start:start+chunk];w=w/w.sum(axis=1,keepdims=True);low=w@lower;high=w@upper
  block=[]
  for p in probabilities:
   left=high<p;right=low>=p;ok=left.any(axis=1)&right.any(axis=1)
   li=np.where(left,np.arange(len(grid)),-1).max(axis=1);ri=np.where(right,np.arange(len(grid)),len(grid)).min(axis=1)
   intervals=np.full((len(w),2),np.nan);intervals[ok,0]=grid[li[ok]];intervals[ok,1]=grid[ri[ok]]
   unbracketed=unbracketed or not ok.all()
   for lo,hi in intervals[ok]:
    if hi-lo>absolute_width:failed.add((float(lo),float(hi)))
   block.append(intervals)
  brackets.append(np.stack(block,axis=1))
 return dict(resolved=not failed and not unbracketed,unbracketed=bool(unbracketed),refine_intervals=sorted(failed),brackets=np.concatenate(brackets),weight_rows=len(matrix),scope='Exactly supplied fixed rows; not all possible weights')
