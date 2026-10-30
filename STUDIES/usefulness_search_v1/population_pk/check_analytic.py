import hashlib,importlib.util,json,time
from pathlib import Path
import numpy as np
from native import Native,ROOT
from involutions import global_exchange,local_exchange
old=Path('/dev/shm/population-jumps-20261029');spec=importlib.util.spec_from_file_location('ode_native',old/'native.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
a=Native();o=module.Native();p=json.loads((ROOT/'PREPARED.json').read_text());m=json.loads((ROOT/'MODES.json').read_text());points=[('primary',np.array(p['mode'])),('secondary',np.array(m['mode']))] if 'mode' in m else [('primary',np.array(p['mode'])),('secondary',np.array(m['secondary_mode']))]
files=[ROOT/'population_analytic.cpp',ROOT/'population.so',ROOT/'native.py',ROOT/'model.py',ROOT/'PREPARED.json',ROOT/'MODES.json',ROOT/'ANALYTIC-PROTOCOL.md',ROOT/'check_analytic.py',old/'population.so']
for folder in sorted((old/'jump01').glob('*/result')):
 path=folder/'draws.npz';files.append(path);q=np.load(path)['q']
 for c in range(4):
  for j in [0,13,26,39]:
   x=q[c,j]
   points.append((f'{folder.parent.name}-{c}-{j}',x))
   points.append(('global',global_exchange(x)))
   for subject in range(12):points.append(('local',local_exchange(x,subject)))
fdpoints=points[:2].copy()
for gap in [0,1e-10,1e-6,1e-3]:
 for sign in [-1,0,1]:
  x=np.array(p['mode']);tau=np.exp(x[3:6]);z=x[6:-1].reshape(12,3);phys=x[:3]+tau*z
  phys[:,1]=phys[:,0]+sign*gap;z[:]=(phys-x[:3])/tau
  points.append((f'equal-{gap}-{sign}',x));fdpoints.append(points[-1])
manifest={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in files};(ROOT/'ANALYTIC-INPUTS.json').write_text(json.dumps(manifest,indent=2)+'\n')
rows=[];fd=[]
for label,x in points:
 va,ga=a.value(x);vo,go=o.value(x);vv=a.density(x)
 rows.append(dict(label=label,offset=va-vo,gradient_error=float(np.max(abs(ga-go)/(1+abs(go)))),value_only_error=abs(vv-va)/(1+abs(va))))
for label,x in fdpoints:
 v,g=a.value(x);h=1e-5;gg=np.empty(43)
 for j in range(43):
  e=np.zeros(43);e[j]=h;gg[j]=(a.density(x+e)-a.density(x-e))/(2*h)
 fd.append(dict(label=label,error=float(np.max(abs(g-gg)/(1+abs(g))))))
timings=[]
for rep in range(5):
 for label,b in ([('analytic',a),('ode',o)] if rep%2 else [('ode',o),('analytic',a)]):
  start=time.perf_counter()
  for _,x in points[:100]:b.value(x)
  timings.append(dict(rep=rep,implementation=label,seconds=time.perf_counter()-start,calls=min(100,len(points))))
r=dict(points=len(rows),max_gradient_error=max(v['gradient_error'] for v in rows),offset_spread=float(np.ptp([v['offset'] for v in rows])),max_value_only_error=max(v['value_only_error'] for v in rows),max_finite_difference_error=max(v['error'] for v in fd),rows=rows,finite_differences=fd,timings=timings,source_unchanged=all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==h for f,h in manifest.items()))
r['passed']=r['max_gradient_error']<=1e-4 and r['offset_spread']<=1e-5 and r['max_value_only_error']<=1e-10 and r['max_finite_difference_error']<=1e-4 and r['source_unchanged']
(ROOT/'ANALYTIC-CHECK.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k not in ['rows','finite_differences']}));a.close();o.close();assert r['passed']
