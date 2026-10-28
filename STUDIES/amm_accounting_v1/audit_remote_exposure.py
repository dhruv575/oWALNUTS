"""Read acquisition metadata only; explicitly inventory excluded archives."""
import hashlib,json,os,time,sys
from pathlib import Path
from datetime import datetime,timezone
from exposure_inventory import eligible,intervals

def run(root,out):
    root=Path(root);out=Path(out);assert not out.exists();start=time.monotonic()
    lo=int(datetime(2025,8,26,tzinfo=timezone.utc).timestamp()*1000)
    hi=int(datetime(2025,11,1,tzinfo=timezone.utc).timestamp()*1000)-1
    records=[];archives=[];skipped=[];errors=[];seen={};count=0
    excluded={'.git','.venv','venv','env','node_modules','site-packages','__pycache__','.cache','runtime-cache'}
    for folder,dirs,files in os.walk(root):
        dirs[:]=[d for d in dirs if d not in excluded]
        if time.monotonic()-start>180:raise TimeoutError('Metadata audit bound')
        for name in files:
            path=Path(folder)/name
            if path.is_symlink():continue
            if name.endswith(('.tar.gz','.tgz','.zip','.tar')):
                archives.append(dict(path=str(path),bytes=path.stat().st_size));continue
            if not eligible(name):continue
            count+=1
            if count>10000:raise RuntimeError('Metadata count bound')
            if path.stat().st_size>4194304:skipped.append(str(path));continue
            raw=path.read_bytes();sha=hashlib.sha256(raw).hexdigest()
            if sha in seen:seen[sha].append(str(path));continue
            seen[sha]=[str(path)]
            try:found=intervals(json.loads(raw))
            except (ValueError,UnicodeError):errors.append(str(path));continue
            if found:records.append(dict(sha256=sha,locations=seen[sha],intervals=found))
    overlaps=[dict(sha256=r['sha256'],locations=r['locations'],interval=x) for r in records for x in r['intervals'] if x['start_ms']<=hi and x['end_ms']>=lo]
    result=dict(root=str(root),candidate_start_ms=lo,candidate_end_ms=hi,metadata_files=count,unique_hashes=len(seen),records=records,overlaps=overlaps,skipped_large=skipped,parse_errors=errors,unexpanded_archives=archives,excluded_directories=sorted(excluded),elapsed_seconds=time.monotonic()-start,scope='Remote metadata only, excluding archive contents and external histories; no prices/returns inspected')
    out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['metadata_files','unique_hashes','elapsed_seconds']}|dict(overlaps=len(overlaps),archives=len(archives),skipped=len(skipped),errors=len(errors))))

if __name__=='__main__':run(*sys.argv[1:])
