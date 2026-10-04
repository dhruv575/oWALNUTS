import json,re,hashlib,subprocess
from pathlib import Path
R=Path('C:/dev/owalnuts').resolve();S=R/'STUDIES/options_flow_v1';O=Path(__file__).resolve().parent
fit=list(range(199010001,199010065))+list(range(199110001,199110065))+list(range(199240001,199240065));bootstrap=[199370001];candidates=set(fit+bootstrap)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):
 with Path(p).open('x') as f:json.dump(v,f,indent=2)
prior=R/'target/posterior-resource-draft/repository-seed-audit-v2.json';base=json.loads(prior.read_text());paths=set(base['inventory_files'])
for name in subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=R).decode().split('\0'):
 if name:paths.add(str((R/name).resolve()))
# Known ignored development declaration roots supplement git's nonignored scope.
for dirname in ['posterior-resource-draft','posterior-resource-recovery-draft','posterior-bank-analysis-design','correlated-reference-draft']:
 for p in (R/'target'/dirname).glob('*'):
  if p.is_file():paths.add(str(p.resolve()))
entries={};excluded=[];hits=[];token=re.compile(r'(?<![\w.])\d[\d_]*(?![\w.])')
for name in sorted(paths):
 p=Path(name)
 if O==p or O in p.parents:excluded.append(dict(path=name,reason='this proposal audit definition/output; not consumed'));continue
 if not p.is_file():excluded.append(dict(path=name,reason='missing'));continue
 if p.suffix.lower() not in ['.py','.rs','.md','.json','.toml','.txt','.yaml','.yml','.ps1','.sh','.csv'] or p.stat().st_size>4000000 or p.name.lower() in ['raw.json','data.json','fixture.json'] or 'raw.json' in p.name.lower() or any(x.lower() in ['raw','draws'] for x in p.parts):excluded.append(dict(path=name,reason='bounded extension/4MB/raw-fixture exclusion'));continue
 b=p.read_bytes()
 try:body=b.decode('utf-16' if b[:2] in [b'\xff\xfe',b'\xfe\xff'] else 'utf-8-sig')
 except UnicodeError:excluded.append(dict(path=name,reason='not UTF8/BOMUTF16'));continue
 entries[str(p.resolve())]=hashlib.sha256(b).hexdigest()
 if '199' in body:
  found=sorted({int(m.group().replace('_','')) for m in token.finditer(body)}&candidates)
  if found:hits.append(dict(path=str(p.resolve()),seeds=found))
supp=O/'repository-supplement.json'
save(supp,dict(status='passed' if not hits else 'review_required',candidate_seeds=sorted(candidates),hits=hits,inventory_files=entries,excluded=excluded,prior_inventory_path=str(prior),prior_inventory_sha256=sha(prior),head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),scope='Prior49118-file inventory plus current tracked/untracked nonignored text and four named ignored development declaration roots; <=4MB,UTF8/BOMUTF16; raw/fixture and other ignored trees excluded; dynamic arithmetic not universally expanded.'))
hist=R/'target/posterior-resource-draft/posterior-resource-seed-audit-v3.json';old=json.loads(hist.read_text());reserved=set(old['reserved_seeds'])|set(old['seeds'])|set(range(1970000000,1970003612));primary={}
for name,h in entries.items():
 p=Path(name)
 try:rel=p.relative_to(S)
 except ValueError:continue
 if p.stat().st_size>2000000:continue
 if (len(rel.parts)==1 and p.suffix=='.py') or (rel.parts[0]=='artifacts' and len(rel.parts)<=3 and p.suffix=='.json' and any(k in p.name.lower() for k in ['plan','seed','protocol','manifest','intent','attest','provenance'])):
  primary[name]=h
  b=p.read_bytes();text=b.decode('utf-16' if b[:2] in [b'\xff\xfe',b'\xfe\xff'] else 'utf-8-sig')
  reserved.update(v for m in token.finditer(text) if (v:=int(m.group().replace('_','')))<2**32)
status='passed' if not hits and not candidates&reserved else 'review_required'
for label,seeds in [('fit',fit),('bootstrap',bootstrap)]:
 save(O/(label+'-seed-audit.json'),dict(status=status,seeds=seeds,hits=hits,inventory_files=primary,reserved_seeds=sorted(reserved),supplemental_evidence={str(supp):sha(supp),str(hist):sha(hist)},auditor='Independent audit agent; prospective proposal only, no streams consumed',scope='Compact current primary with immutable repository supplement. Prior allocated193/194/195/197 and198pilot retained through historical reserved sets. Primary source refresh required after final integration; separate192fit and1bootstrap stream families.'))
print(json.dumps(dict(status=status,primary=len(primary),supplemental=len(entries),reserved=len(reserved),hits=hits)))
