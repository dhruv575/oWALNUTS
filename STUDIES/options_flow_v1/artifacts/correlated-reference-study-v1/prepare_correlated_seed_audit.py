from pathlib import Path
import json,hashlib,re,subprocess
R=Path('C:/dev/owalnuts');S=R/'STUDIES/options_flow_v1';O=S/'artifacts/correlated-reference-study-v1';O.mkdir(exist_ok=False);sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
base=json.loads((S/'artifacts/persistent-comparison-v1/seed-audit.json').read_text());inventory={};hits=[];skipped=[]
paths=set(base['inventory_files'])
for name in subprocess.check_output(['git','ls-files','-z'],cwd=R).decode().split('\0'):
 p=R/name
 if name and p.is_file() and p.suffix.lower() in base['scope']['text_extensions'] and p.stat().st_size<=4_000_000 and p.name not in ('raw.json','data.json','fixture.json') and not any(x.lower() in ('raw','draws') for x in p.parts):paths.add(str(p.resolve()))
for name in sorted(paths):
 p=Path(name)
 if not p.exists() or O in p.parents:continue
 try:body=p.read_text(encoding='utf-8-sig')
 except UnicodeError:skipped.append(name);continue
 inventory[name]=sha(p)
 for m in re.finditer(r'(?<!\d)197000\d{4}(?!\d)',body):
  n=int(m.group())
  if 1970000000<=n<=1970003611:hits.append(dict(path=name,seed=n))
assert not hits,hits
supp=O/'repository-seed-audit.json';supp.write_text(json.dumps(dict(status='passed',candidate_seeds=list(range(1970000000,1970003612)),inventory_files=inventory,hits=[],scope=base['scope'],skipped_unicode=skipped,current_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()),indent=2))
primary={};reserved=set()
prior=S/'artifacts/reference-bank-allocation-vectorized-60min-v1/historical-seed-inventory.json';reserved.update(json.loads(prior.read_text())['reserved_seeds'])
for p in S.glob('*.py'):primary[str(p.resolve())]=sha(p)
for p in (S/'artifacts').rglob('*.json'):
 rel=p.relative_to(S)
 if O in p.parents or len(rel.parts)>3 or p.stat().st_size>4_000_000 or not any(k in p.name.lower() for k in ('plan','seed','protocol','manifest','intent','attest','provenance')):continue
 primary[str(p.resolve())]=sha(p)
for p in primary:
 reserved.update(int(m.group()) for m in re.finditer(r'(?<!\d)\d+(?!\d)',Path(p).read_text(encoding='utf-8-sig')) if int(m.group())<2**32)
for start in [1930000000,1940000000,1950000000]:reserved.update(range(start,start+11156))
reserved.update([196120001,196120002,196120003,196120011,196120012,196120013,196250001,196250002,196250003,196250011,196250012,196250013]);reserved.update(range(106510001,106510007));reserved.update(range(106640001,106640007));reserved.update([106380001,106380002])
assert not set(range(1970000000,1970003612))&reserved
primary[str(supp)]=sha(supp);primary[str(prior)]=sha(prior)
audit=dict(status='passed',candidate_seeds=list(range(1970000000,1970003612)),reserved_seeds=sorted(reserved),inventory_files=primary,auditor='Bounded exact-token primary plus immutable repository supplemental; independent review pending',scope='Primary top-level studyPython and campaign-root named declarationJSON up to4MB; conservative all uint32 numeric tokens reserved, supplemented by prior fullinventory and all193/194/195allocated streams includingunstarted,196smoke+106persistent streams. Repository supplement hash-only evidence, contains candidate definitions not historicalconsumption; UTF8 scope/skips recorded.',supplemental_evidence={str(supp):sha(supp)},hits=[])
(O/'historical-seed-inventory.json').write_text(json.dumps(audit,indent=2));print(json.dumps(dict(primary=len(primary),supplemental=len(inventory),reserved=len(reserved),candidate=3612,hits=0)))
