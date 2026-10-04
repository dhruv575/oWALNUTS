from pathlib import Path
import json,hashlib,re,subprocess,shutil
R=Path('C:/dev/owalnuts');S=R/'STUDIES/options_flow_v1';O=S/'artifacts/persistent-comparison-v1';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
old=json.loads((O/'seed-audit-compact.json').read_text());broad=json.loads((O/'seed-audit.json').read_text());vals=old['seeds'];pat=re.compile(r'(?<!\d)(?:'+'|'.join(map(str,vals))+r')(?!\d)')
changed=subprocess.check_output(['git','diff','--name-only',broad['scope']['head'],'HEAD'],cwd=R,text=True).splitlines();delta={};hits=[];exempt=[];skipped=[]
for name in changed:
 p=R/name
 if not p.is_file():continue
 if O in p.parents:exempt.append(dict(path=name,reason='Current proposal/audit/initialized fixture lineage, expected declared14streams'));continue
 if p.suffix.lower() not in broad['scope']['text_extensions'] or p.stat().st_size>4_000_000:skipped.append(name);continue
 try:text=p.read_text(encoding='utf-8-sig')
 except UnicodeError:skipped.append(name);continue
 delta[str(p)]=sha(p)
 for m in pat.finditer(text):hits.append(dict(path=name,seed=int(m.group())))
assert not hits,hits
refresh=dict(status='passed',base_supplemental_sha256=sha(O/'seed-audit.json'),base_head=broad['scope']['head'],head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),inventory_files=delta,hits=hits,explicit_exemptions=exempt,excluded_nontext_or_oversize=skipped,seeds=vals)
(O/'seed-supplemental-refresh-v2.json').write_text(json.dumps(refresh,indent=2))
inv={}
for p in S.glob('*.py'):inv[str(p.resolve())]=sha(p)
for p in (S/'artifacts').rglob('*.json'):
 rel=p.relative_to(S)
 if O in p.parents or len(rel.parts)>3 or p.stat().st_size>4_000_000 or not any(k in p.name.lower() for k in ('plan','seed','protocol','manifest','intent','attest','provenance')):continue
 inv[str(p.resolve())]=sha(p)
for name in inv:
 assert not pat.search(Path(name).read_text(encoding='utf-8-sig')),name
new=dict(old,inventory_files=inv,supplemental_evidence={str(O/'seed-audit.json'):sha(O/'seed-audit.json'),str(O/'seed-supplemental-refresh-v2.json'):sha(O/'seed-supplemental-refresh-v2.json')});new['scope']=dict(old['scope'],refresh='Current main primary regenerated; changed tracked text since original broad HEAD audited separately with explicit current proposal lineage exclusions.');(O/'seed-audit-compact-v2.json').write_text(json.dumps(new,indent=2))
for name in ['prepare_persistent_seed_audit.py','compact_persistent_seed_audit.py','prepare_persistent_fixtures.py','refresh_persistent_audit.py']:
 src=R/'target'/name
 if src.exists():shutil.copyfile(src,O/name)
print(json.dumps(dict(primary=len(inv),delta=len(delta),hits=hits,exemptions=len(exempt))))
