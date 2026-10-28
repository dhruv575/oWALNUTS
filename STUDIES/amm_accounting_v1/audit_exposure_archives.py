"""Scan listed archives for acquisition metadata without parsing market payloads."""
import json,hashlib,tarfile,zipfile,time,sys
from pathlib import Path
from exposure_inventory import eligible,intervals

def run(inventory,output):
    inv=json.loads(Path(inventory).read_text());start=time.monotonic();records=[];errors=[];missing=[];large=[];nested=[];scanned=[]
    lo=inv['candidate_start_ms'];hi=inv['candidate_end_ms']
    def consume(raw,label):
        found=intervals(json.loads(raw))
        if found:records.append(dict(location=label,sha256=hashlib.sha256(raw).hexdigest(),intervals=found))
    for item in inv['unexpanded_archives']:
        p=Path(item['path'])
        if not p.exists():missing.append(str(p));continue
        try:
            if time.monotonic()-start>240:raise TimeoutError('Archive scan time bound')
            if p.suffix=='.zip':
                with zipfile.ZipFile(p) as archive:
                    for m in archive.infolist():
                        if m.filename.endswith(('.zip','.tar.gz','.tgz','.tar')):nested.append(str(p)+'!'+m.filename)
                        if not eligible(m.filename):continue
                        if m.file_size>4194304:large.append(str(p)+'!'+m.filename);continue
                        consume(archive.read(m),str(p)+'!'+m.filename)
            else:
                with tarfile.open(p,'r|*') as archive:
                    for m in archive:
                        if time.monotonic()-start>240:raise TimeoutError('Archive scan time bound')
                        if not m.isfile():continue
                        if m.name.endswith(('.zip','.tar.gz','.tgz','.tar')):nested.append(str(p)+'!'+m.name)
                        if not eligible(m.name):continue
                        if m.size>4194304:large.append(str(p)+'!'+m.name);continue
                        consume(archive.extractfile(m).read(),str(p)+'!'+m.name)
            scanned.append(str(p))
        except Exception as e:errors.append(dict(path=str(p),error=type(e).__name__))
    overlaps=[dict(location=r['location'],interval=x) for r in records for x in r['intervals'] if x['start_ms']<=hi and x['end_ms']>=lo]
    result=dict(scanned=scanned,records=records,overlaps=overlaps,missing=missing,oversized_metadata=large,nested_archives=nested,errors=errors,elapsed_seconds=time.monotonic()-start,scope='Metadata members only; nested archives inventoried but not expanded; no market payload values parsed')
    Path(output).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(scanned=len(scanned),overlaps=len(overlaps),errors=len(errors),missing=len(missing),nested=len(nested))))

if __name__=='__main__':run(*sys.argv[1:])
