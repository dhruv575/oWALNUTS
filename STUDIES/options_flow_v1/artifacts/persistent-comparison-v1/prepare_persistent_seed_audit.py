from pathlib import Path
import subprocess,json,re,hashlib
ROOT=Path('C:/dev/owalnuts');STUDY=ROOT/'STUDIES/options_flow_v1';OUT=STUDY/'artifacts/persistent-comparison-v1'
OUT.mkdir(exist_ok=False)
seeds=list(range(106510001,106510007))+list(range(106640001,106640007))+[106380001,106380002]
pattern=re.compile(r'(?<!\d)(?:'+'|'.join(map(str,seeds))+r')(?!\d)')
tracked=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0');inventory={};hits=[];excluded=[]
text_ext={'.py','.rs','.toml','.md','.json','.yaml','.yml','.txt','.csv','.sh','.ps1','.lock'}
keywords=('plan','seed','protocol','manifest','summary','provenance','attest','status','intent')
candidates=set()
for name in tracked:
 p=ROOT/name
 if not name or not p.is_file():continue
 if p.suffix.lower() not in text_ext:continue
 # Draws/raw/cell evidence are numerical artifacts, never seed declarations.
 if any(part.lower() in ('draws','raw') for part in p.parts) or p.name.lower() in ('raw.json','data.json','fixture.json') or p.name.lower().endswith('-raw.json'):
  excluded.append(dict(path=name,reason='raw numerical/fixture payload'));continue
 if p.stat().st_size>4_000_000:excluded.append(dict(path=name,reason='text over4MB bounded scan'));continue
 candidates.add(p)
for p in STUDY.rglob('*'):
 if not p.is_file() or OUT in p.parents:continue
 if p.suffix=='.py' or (p.suffix=='.json' and any(k in p.name.lower() for k in keywords)):
  if p.stat().st_size<=4_000_000:candidates.add(p)
  else:excluded.append(dict(path=str(p.relative_to(ROOT)),reason='historical metadata over4MB'))
for p in sorted(candidates):
 try:body=p.read_text(encoding='utf-8-sig')
 except UnicodeError:continue
 inventory[str(p.resolve())]=hashlib.sha256(p.read_bytes()).hexdigest()
 for match in pattern.finditer(body):hits.append(dict(path=str(p),seed=int(match.group()),line=body[:match.start()].count('\n')+1))
audit=dict(status='passed' if not hits else 'failed',seeds=seeds,hits=hits,scope=dict(primary='All historical study Python and named JSON containing plan/seed/protocol/manifest/summary/provenance/attest/status/intent up to4MB, including untracked historical metadata; excludes this new output directory.',supplement='All git-tracked repository text extensions listed up to4MB; numerical raw/fixture payload exclusions explicit. Exact integer-token matching, not raw-array scan.',text_extensions=sorted(text_ext),excluded=excluded,head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()),auditor='Bounded exact-token inventory generated before initialization or sampling; independent review pending',inventory_files=inventory,sampler_rows=[seeds[:3],seeds[3:6]],initialization_seeds=seeds[-2:])
(OUT/'seed-audit.json').write_text(json.dumps(audit,indent=2));print(json.dumps(dict(status=audit['status'],files=len(inventory),hits=hits,excluded=len(excluded))))
