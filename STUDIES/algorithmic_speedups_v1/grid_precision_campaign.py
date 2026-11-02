import json,shutil
from followup_campaign import BASE,PY
from resource_monitor import execute
if __name__=='__main__':
    assert shutil.disk_usage(BASE).free>1024**3
    out=BASE/'grid_precision01/nuts_grid-954100004';out.mkdir(parents=True,exist_ok=False)
    result=execute([PY,str(BASE/'grid_precision_worker.py'),'nuts_grid','954100004',str(out/'artifact')],BASE,900,out,2*1024**3,32*1024**2,out/'worker.log',output_scan_interval=2.)
    (out/'SUPERVISION.json').write_text(json.dumps(result,indent=2))
    (BASE/'GRID-PRECISION-STATUS.json').write_text(json.dumps(result,indent=2))
