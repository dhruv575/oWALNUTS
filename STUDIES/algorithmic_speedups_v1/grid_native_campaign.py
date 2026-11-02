import concurrent.futures as cf,json,time,shutil
from followup_campaign import run,BASE,PY
if __name__=='__main__':
    assert json.loads((BASE/'GRID-NATIVE-PREFLIGHT.json').read_text())['passed']
    # Wait for both four-core reference controls to drain before reserving 8.
    while not (BASE/'FOLLOWUP-STATUS.json').exists():time.sleep(5)
    assert shutil.disk_usage(BASE).free>1024**3
    with cf.ThreadPoolExecutor(max_workers=2) as pool:
        jobs=[pool.submit(run,'grid_native_worker.py','nuts_grid',s,'grid_native01',PY) for s in [954100001,954100002]]
        rows=[f.result() for f in jobs]
    (BASE/'GRID-NATIVE-STATUS.json').write_text(json.dumps(rows,indent=2))
