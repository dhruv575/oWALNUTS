from followup_campaign import run,PHYS,BASE
import concurrent.futures as cf
import json,hashlib
def main():
    (BASE/'PHYSICS-REPAIR01-SOURCES.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in BASE.iterdir() if p.suffix in ['.py','.cpp','.so']},indent=2))
    pre=run('physics_worker.py','prepare',954200000,'physics_repair01',PHYS)
    if pre['exit_code']!=0:return
    methods=['mh_affine','da_affine','mh_transport','da_transport','nuts_raw','nuts_affine','nuts_transport','walnuts_raw','walnuts_affine','walnuts_transport']
    with cf.ThreadPoolExecutor(max_workers=2) as pool:
        jobs=[pool.submit(run,'physics_worker.py',m,s,'physics_repair01',PHYS) for m in methods for s in [954200001,954200002]]
        rows=[pre]+[f.result() for f in jobs]
    (BASE/'PHYSICS-REPAIR01-STATUS.json').write_text(json.dumps(rows,indent=2))
if __name__=='__main__':main()
