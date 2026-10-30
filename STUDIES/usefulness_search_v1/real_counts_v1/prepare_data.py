import ast,hashlib,json
from pathlib import Path
p=Path(__file__).resolve().parent;source=p/'source/marginalizing-models.ipynb';provenance=json.loads((p/'source/PROVENANCE.json').read_text(encoding='utf-8-sig'));assert hashlib.sha256(source.read_bytes()).hexdigest()==provenance['notebook_sha256'];book=json.loads(source.read_text());matches=[]
for cell in book['cells']:
 text=''.join(cell.get('source',[]))
 if cell.get('cell_type')=='code' and 'disaster_data = pd.Series(' in text:
  tree=ast.parse(text);assignments={node.targets[0].id:node.value for node in tree.body if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name)}
  if 'years' in assignments:matches.append((text,assignments))
assert len(matches)==1;text,a=matches[0];series=a['disaster_data'];assert isinstance(series,ast.Call) and ast.unparse(series.func)=='pd.Series' and isinstance(series.args[0],ast.List)
counts=[]
for node in series.args[0].elts:
 if isinstance(node,ast.Constant) and isinstance(node.value,int) and node.value>=0:counts.append(node.value)
 else:assert ast.unparse(node)=='np.nan';counts.append(None)
years=a['years'];assert isinstance(years,ast.Call) and ast.unparse(years.func)=='np.arange';start,end=[ast.literal_eval(x) for x in years.args];assert (start,end)==(1851,1962) and len(counts)==end-start and counts.count(None)==2
rows=[dict(year=year,count=value) for year,value in zip(range(start,end),counts)];out=p/'data01';out.mkdir(exist_ok=False)
(out/'ALL.json').write_text(json.dumps(rows,indent=2)+'\n');train=[x for x in rows if x['year']<=1930];test=[x for x in rows if x['year']>1930]
for name,data in [('TRAIN.json',train),('HELDOUT.json',test)]: (out/name).write_text(json.dumps(data,indent=2)+'\n')
observed=[x for x in train if x['count'] is not None];target=dict(N=len(observed),x=[20*(x['year']-1851)/(1930-1851) for x in observed],k=[x['count'] for x in observed]);(out/'GP-TRAIN.json').write_text(json.dumps(target,indent=2)+'\n')
result=dict(passed=True,rows=len(rows),observed=sum(x['count'] is not None for x in rows),train_observed=len(observed),heldout_observed=sum(x['count'] is not None for x in test),missing_years=[x['year'] for x in rows if x['count'] is None],year_range=[start,end-1],source=provenance,hashes={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in out.iterdir() if f.is_file()})
(out/'MANIFEST.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['passed','rows','observed','train_observed','heldout_observed','missing_years','year_range']}))
