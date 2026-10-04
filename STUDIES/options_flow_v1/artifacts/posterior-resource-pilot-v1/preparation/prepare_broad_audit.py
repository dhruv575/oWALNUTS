import json,re,hashlib,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[2];S=R/'STUDIES/options_flow_v1';O=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
rows=json.loads((O/'posterior-resource-streams-v1.json').read_text());seeds=[r[k] for r in rows for k in ['init_seed','seed','predictive_seed']]
pat=re.compile(r'(?<![0-9])(?:'+'|'.join(map(str,seeds))+r')(?![0-9])')
prior=S/'artifacts/correlated-reference-study-v1/repository-seed-audit.json';base=json.loads(prior.read_text());paths=set(base['inventory_files'])
# Add current tracked and untracked declaration/code paths, excluding ignored build trees.
for name in subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=R).decode().split('\0'):
 if name:paths.add(str((R/name).resolve()))
entries={};excluded=[];hits=[]
for name in sorted(paths):
 p=Path(name)
 if not p.is_file():excluded.append(dict(path=name,reason='missing'));continue
 if p.suffix.lower() not in ['.py','.rs','.md','.json','.toml','.txt','.yaml','.yml','.ps1','.sh','.csv'] or p.stat().st_size>4000000 or p.name.lower() in ['raw.json','data.json','fixture.json'] or any(x.lower() in ['raw','draws'] for x in p.parts) or 'raw.json' in p.name.lower():excluded.append(dict(path=name,reason='bounded extension/size/raw-fixture exclusion'));continue
 try:body=p.read_text(encoding='utf-8-sig')
 except UnicodeError:excluded.append(dict(path=name,reason='nonUTF8'));continue
 entries[str(p.resolve())]=sha(p)
 if pat.search(body):hits.append(dict(path=name,seeds=sorted(set(pat.findall(body)))))
assert not hits,hits
supp=O/'repository-seed-audit-v2.json';supp.write_text(json.dumps(dict(status='passed',seeds=seeds,hits=hits,inventory_files=entries,excluded=excluded,prior_inventory_path=str(prior),prior_inventory_sha256=sha(prior),scope='Prior repository inventory plus current git tracked/untracked nonignored files; UTF8 text <=4MB with explicit exclusions; no raw arrays.'),indent=2))
primary={}
for name,h in entries.items():
 p=Path(name)
 try:rel=p.relative_to(S)
 except ValueError:continue
 if p.stat().st_size>2000000:continue
 if (len(rel.parts)==1 and p.suffix=='.py') or (rel.parts[0]=='artifacts' and len(rel.parts)<=3 and p.suffix=='.json' and any(k in p.name.lower() for k in ['plan','seed','protocol','manifest','intent','attest','provenance'])):primary[name]=h
hist=S/'artifacts/correlated-reference-study-v1/historical-seed-inventory.json';old=json.loads(hist.read_text());reserved=set(old['reserved_seeds']);reserved.update(range(1970000000,1970003612))
assert not set(seeds)&reserved
out=dict(status='passed',seeds=seeds,hits=[],inventory_files=primary,reserved_seeds=sorted(reserved),supplemental_evidence={str(supp):sha(supp),str(hist):sha(hist)},auditor='Model agent bounded exact-token repository refresh; independent review pending',scope='Compact <=2MB study/campaign declaration primary plus hash-bound refreshed repository supplement. All 197 allocated streams reserved including unstarted cells. Excludes raw/large/nonUTF8/ignored external histories; no universal uniqueness claim.')
(O/'posterior-resource-seed-audit-v2.json').write_text(json.dumps(out,indent=2));print(json.dumps(dict(primary=len(primary),supplemental=len(entries),excluded=len(excluded),hits=hits,reserved=len(reserved))))
