from pathlib import Path
import json,re,hashlib
R=Path('C:/dev/owalnuts');S=R/'STUDIES/options_flow_v1';O=S/'artifacts/persistent-comparison-v1'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
supp=O/'seed-audit.json';old=json.loads(supp.read_text());values=old['seeds'];pat=re.compile(r'(?<!\d)(?:'+'|'.join(map(str,values))+r')(?!\d)');inventory={};hits=[]
# Primary: study Python plus campaign-root declaration files, not per-fit repeats.
for name,h in old['inventory_files'].items():
 p=Path(name)
 try:rel=p.relative_to(S)
 except ValueError:continue
 selected=(len(rel.parts)==1 and p.suffix=='.py') or (rel.parts[0]=='artifacts' and len(rel.parts)<=3 and p.suffix=='.json' and any(k in p.name.lower() for k in ('plan','seed','protocol','manifest','intent','attest','provenance')))
 if not selected or O in p.parents:continue
 if sha(p)!=h:raise ValueError('Historical primary changed: '+name)
 inventory[name]=h
 for m in pat.finditer(p.read_text(encoding='utf-8-sig')):hits.append(dict(path=name,seed=int(m.group())))
assert not hits
scope={'primary':'Top-level study Python and campaign-root JSON declaration files (artifacts/<campaign>/<file> or artifacts/<file>) containing plan/seed/protocol/manifest/intent/attest/provenance. Excludes per-fit reports/status repeating plans. Uses original full inventory4MB cap; no raw arrays.','supplement':'Original48,973-file repository scan preserved unchanged and hash-bound, UTF-8 decodable text only; Unicode decode failures were skipped and not enumerated in original scan. This scope limitation is explicit; no claim of binary/non-UTF8 search.'}
compact=dict(status='passed',seeds=values,hits=[],scope=scope,auditor='Bounded exact-token primary scan plus immutable broad supplemental; independent review pending',inventory_files=inventory,supplemental_evidence={str(supp):sha(supp)},sampler_rows=old['sampler_rows'],initialization_seeds=old['initialization_seeds'])
(O/'seed-audit-compact.json').write_text(json.dumps(compact,indent=2));print(len(inventory))
