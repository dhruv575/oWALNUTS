"""Bounded exact integer-token source/metadata scan, never raw payloads or RNG."""
import argparse,hashlib,json,os,re,subprocess,time
from pathlib import Path
EXCLUDE={'artifacts','draws','raw','data','datasets','vendor','node_modules','target','evidence','.git','__pycache__','.venv','venv','build','dist','outputs','site-packages'}
def selected(rel):
    p=Path(rel)
    if set(x.lower() for x in p.parts)&EXCLUDE:return False
    return p.suffix.lower() in {'.py','.rs','.md','.toml'} or p.suffix.lower()=='.json' and any(k in p.name.lower() for k in ('manifest','protocol','seed','config'))
def scan(main,inventory,seconds=30,max_files=5000):
    start=time.monotonic();raw=Path(inventory).read_bytes();v=json.loads(raw);seeds={x for group in v['month_roles'].values() for values in group.values() for x in values};roots=[str(Path(main).absolute())];discovery=[];hits=[];skipped=[];digests=set();checked=0;bytes_checked=0;stopped=None
    listing=subprocess.check_output(['git','worktree','list','--porcelain'],cwd=main,timeout=5).decode()
    roots+= [line[len('worktree '):] for line in listing.splitlines() if line.startswith('worktree ') and line[len('worktree '):] not in roots]
    token=re.compile(r'(?<![\w.])\d(?:[\d_]*\d)?(?![\w.])')
    for root in roots:
        if time.monotonic()-start>=seconds:stopped='time_bound';break
        try:names=subprocess.check_output(['git','ls-files','-z'],cwd=root,timeout=max(.1,seconds-(time.monotonic()-start))).decode().split('\0')
        except Exception as exc:discovery.append(dict(root=root,error=repr(exc)));continue
        candidates={n for n in names if n and selected(n)}
        # Include ignored named protocol/run metadata, pruning numerical payload trees.
        for path,dirs,files in os.walk(Path(root)/'STUDIES'):
            dirs[:]=[d for d in dirs if d.lower() not in EXCLUDE]
            if time.monotonic()-start>=seconds:stopped='time_bound';break
            for name in files:
                rel=str((Path(path)/name).relative_to(root))
                if Path(name).suffix.lower()=='.json' and selected(rel):candidates.add(rel)
        discovery.append(dict(root=root,selected=len(candidates)))
        for name in sorted(candidates):
            if checked>=max_files or time.monotonic()-start>=seconds:stopped='file_or_time_bound';break
            p=Path(root)/name
            try:
                if p.stat().st_size>2*1024**2:
                    if len(skipped)<100:skipped.append(dict(root=root,path=name,reason='over_2MiB'))
                    continue
                content=p.read_bytes()
            except OSError:continue
            digest=hashlib.sha256(content).digest()
            if digest in digests:continue
            digests.add(digest);checked+=1;bytes_checked+=len(content);count=sum(int(m.group().replace('_','')) in seeds for m in token.finditer(content.decode('utf8',errors='replace')))
            if count:
                if len(hits)>=50:stopped='hit_record_bound';break
                hits.append(dict(root=root,path=name,matching_token_count=count,expected_new_study=('market_replication' in name)))
        if stopped:break
    return dict(inventory_sha256=hashlib.sha256(raw).hexdigest(),reserved_unique=len(seeds),limits=dict(seconds=seconds,unique_files=max_files,max_file_bytes=2*1024**2,max_hit_records=50),roots_discovery=discovery,checked_unique_files=checked,checked_bytes=bytes_checked,elapsed_seconds=time.monotonic()-start,stopped=stopped,skipped=skipped,hits=hits,scope='Tracked project source/docs and named JSON metadata plus ignored named study metadata; identical blobs deduplicated. Raw/data/draw/evidence/dependency/build trees excluded. Exact decimal integer lexical tokens only, including separators. Partial bounded coverage is preserved; no universal historical or opaque internal-RNG proof.')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('main');p.add_argument('inventory');p.add_argument('output');a=p.parse_args();result=scan(a.main,a.inventory)
    with Path(a.output).open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({k:result[k] for k in ('reserved_unique','checked_unique_files','elapsed_seconds','stopped','hits')}))
