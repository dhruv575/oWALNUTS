import concurrent.futures as cf,json
from followup_campaign import run,PHYS,BASE
if __name__=='__main__':
    methods=['nuts_raw','nuts_affine','nuts_transport','walnuts_raw','walnuts_affine','walnuts_transport']
    with cf.ThreadPoolExecutor(max_workers=2) as pool:
        jobs=[pool.submit(run,'physics_precision_worker.py',m,s,'physics_precision01',PHYS) for m in methods for s in [954200001,954200002]]
        rows=[f.result() for f in jobs]
    (BASE/'PHYSICS-PRECISION01-STATUS.json').write_text(json.dumps(rows,indent=2))
