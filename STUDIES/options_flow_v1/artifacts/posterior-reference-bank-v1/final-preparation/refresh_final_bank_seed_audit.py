"""Run only after portable bank source-final notice. Writes new audits, never overwrites."""
from pathlib import Path
import json,re,hashlib,subprocess
R=Path('C:/dev/owalnuts').resolve();S=R/'STUDIES/options_flow_v1';OLD=S/'artifacts/posterior-reference-bank-v1/preparation';OUT=OLD.parent/'final-preparation'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):
 with Path(p).open('x') as f:json.dump(v,f,indent=2)
if OUT.exists():raise ValueError('Fresh output required; no overwrite')
base=json.loads((OLD/'repository-supplement.json').read_text());fit=json.loads((OLD/'fit-seed-audit.json').read_text());boot=json.loads((OLD/'bootstrap-seed-audit.json').read_text());candidates=set(fit['seeds']+boot['seeds']);assert len(candidates)==193
# Only current proposal preparation/history and explicit handoff prose are exempt;
# test/source hits are NOT silently waived and must receive independent review.
exemption_roots=[OLD,OUT];exemption_files={R/'target/posterior-bank-analysis-design/FRESH_BANK_HANDOFF.md'}
paths=set(subprocess.check_output(['git','diff','--name-only',base['head'],'HEAD'],cwd=R,text=True).splitlines())
paths.update(subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=R,text=True).splitlines())
paths.update(str(p.relative_to(R)) for p in S.rglob('*.py') if 'artifacts' not in p.relative_to(S).parts)
primary={};delta={};hits=[];exempt=[];skipped=[];token=re.compile(r'(?<![\w.])\d[\d_]*(?![\w.])');reserved=set(fit['reserved_seeds'])|set(boot['reserved_seeds'])
for name in sorted(paths):
 p=(R/name).resolve()
 if any(q==p or q in p.parents for q in exemption_roots) or p in exemption_files:exempt.append(str(p));continue
 if not p.is_file() or p.suffix.lower() not in ['.py','.rs','.md','.json','.toml','.txt','.yaml','.yml','.ps1','.sh','.csv'] or p.stat().st_size>4000000 or p.name in ['raw.json','data.json','fixture.json'] or 'raw.json' in p.name.lower() or any(x.lower() in ['draws','raw'] for x in p.parts):skipped.append(str(p));continue
 b=p.read_bytes()
 try:text=b.decode('utf-16' if b[:2] in [b'\xff\xfe',b'\xfe\xff'] else 'utf-8-sig')
 except UnicodeError:skipped.append(str(p));continue
 delta[str(p)]=sha(p);numbers={int(m.group().replace('_','')) for m in token.finditer(text)}
 if numbers&candidates:hits.append(dict(path=str(p),seeds=sorted(numbers&candidates),classification='unreviewed; could be proposal/mock/actual use, never automatically excluded'))
for name in fit['inventory_files']:
 p=Path(name)
 if p.exists():primary[name]=sha(p)
for p in S.rglob('*.py'):
 if 'artifacts' not in p.relative_to(S).parts:primary[str(p.resolve())]=sha(p)
for name in primary:
 b=Path(name).read_bytes();text=b.decode('utf-16' if b[:2] in [b'\xff\xfe',b'\xfe\xff'] else 'utf-8-sig');numbers={int(m.group().replace('_','')) for m in token.finditer(text)};reserved.update(n for n in numbers if n<2**32)
 if numbers&candidates and not any(h['path']==name for h in hits):hits.append(dict(path=name,seeds=sorted(numbers&candidates),classification='unreviewed primary collision'))
OUT.mkdir();supp=OUT/'delta-repository-audit.json';save(supp,dict(status='passed' if not hits else 'review_required',base_head=base['head'],head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),candidate_seeds=sorted(candidates),inventory_files=delta,hits=hits,exemptions=exempt,skipped=skipped,scope='Changed tracked text since original immutable repository supplement plus nonignored untracked and recursive studyPython; <=4MB UTF8/BOMUTF16. Exact numeric tokens; dynamic arithmetic not universal. Explicit proposal exemptions only.'))
for label,a in [('fit',fit),('bootstrap',boot)]:
 evidence=dict(a['supplemental_evidence']);evidence[str(supp)]=sha(supp)
 save(OUT/f'{label}-seed-audit.json',dict(a,status='passed' if not hits and not candidates&reserved else 'review_required',inventory_files=primary,reserved_seeds=sorted(reserved),hits=hits,supplemental_evidence=evidence,auditor='Final source refresh; independent review required before freeze'))
print(json.dumps(dict(status='passed' if not hits else 'review_required',primary=len(primary),delta=len(delta),candidate_count=193,hits=hits)))
