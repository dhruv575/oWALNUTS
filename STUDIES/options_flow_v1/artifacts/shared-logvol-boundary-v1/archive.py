import hashlib,json,shutil,zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[2];src=Path(__file__).parent
out=root/'STUDIES/options_flow_v1/artifacts/shared-logvol-boundary-v1';out.mkdir()
sha=lambda b:hashlib.sha256(b).hexdigest()
c=json.loads((src/'config.json').read_text());inventory=[];missing=[]
alternates={}
for directory in [root/'STUDIES/options_flow_v1/artifacts/shared-logvol-integration-v1/final-source',root/'target/shared-logvol-integration-tier-v2/pre-edit']:
 for p in directory.glob('*.py'):alternates[sha(p.read_bytes())]=(p.read_bytes(),str(p))
with zipfile.ZipFile(root/'STUDIES/options_flow_v1/artifacts/mixed-target-optimization-v4/executed-sources.zip') as z:
 for n in z.namelist():
  if n.endswith('.py'):
   b=z.read(n);alternates.setdefault(sha(b),(b,'mixed-target-optimization-v4/executed-sources.zip!'+n))
with zipfile.ZipFile(out/'executed-sources.zip','w',zipfile.ZIP_DEFLATED) as z:
 for original,digest in c['bindings'].items():
  p=Path(original)
  if p.suffix!='.py':continue
  b=p.read_bytes() if p.exists() else b'';origin=original
  if sha(b)!=digest:
   match=alternates.get(digest)
   if match is None:missing.append(original);continue
   b,origin=match
  assert sha(b)==digest
  name=('study/' if p.parent.name=='options_flow_v1' else 'other/')+p.name
  z.writestr(name,b);inventory.append(dict(original_path=original,archive_entry=name,sha256=digest,recovered_from=origin))
for n in ['check.py','config.json','result.json','archive.py']:shutil.copyfile(src/n,out/n)
(out/'origin-inventory.json').write_text(json.dumps(dict(sources=inventory,missing=missing,scope='Every archived source byte independently matches the executed boundary config. Runtime binary and interpreter remain bound by config; not duplicated in this source zip.'),indent=2))
(out/'RESULTS.md').write_text('Fixed integrated-builder numerical-domain check: 18 cases, zero candidate-only rejections, six shared nonfinite value/gradient cases. The original y and h grid is preserved. Actual imported adapter bbbb9384 and extension e1331c8d identities were checked before compilation and after execution. The scalar normalized-value oracle uses stable log-domain softplus. This does not establish global numerical safety, sampler reliability, workflow speed, or calibration. Known extreme-domain failures remain. Full finite/rejection rows and value errors are retained in result.json. No rerun was performed for this archive.\n')
(out/'.gitattributes').write_text('* -text\n')
files={p.name:sha(p.read_bytes()) for p in out.iterdir() if p.is_file()}
(out/'checksums.json').write_text(json.dumps(files,indent=2))
print(json.dumps(dict(archived_sources=len(inventory),missing=missing,path=str(out))))
if missing:raise SystemExit(1)
