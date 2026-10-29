"""Select settings from calibration only; never read held-out results."""
import json,sys,statistics,hashlib
from pathlib import Path
from targets import NAMES
from sampling import CONFIGS


def run(root,out):
    root=Path(root);final=json.loads((root/'FINAL.json').read_text());assert len(final['jobs'])==126 and final['sources_unchanged']
    rows=[json.loads(p.read_text()) for p in root.glob('*/result/RESULT.json')]
    choices={};ranks={}
    for name in NAMES:
        choices[name]={};ranks[name]={}
        for engine in ['nuts','walnuts']:
            options=[]
            for config,c in CONFIGS.items():
                if c['engine']!=engine:continue
                subset=[r for r in rows if r['name']==name and r['config']==config]
                good=[r for r in subset if r.get('status')=='ok'];passes=sum(r['metrics']['passed'] for r in good)
                quality=[]
                for r in good:
                    m=r['metrics'];quality.append(max(m['max_error_ratio'] or 1e6,m['max_mcse_ratio'] or 1e6,((m['rhat_max'] or 100)-1)/.01,400/max(m['ess_min'] or 0,1e-9),1+int(m['divergences']>0)+int(m['depth_hits']>0)))
                seconds=statistics.median(r['total_seconds'] for r in good) if good else 1e9
                quality=statistics.median(quality) if quality else 1e9
                rank=(-passes,seconds if passes==2 else quality,seconds,config)
                options.append((rank,config));ranks[name][config]=dict(completed=len(good),passed=passes,median_quality=quality,median_total_seconds=seconds)
            choices[name][engine]=min(options)[1]
    result=dict(selected=choices,calibration=ranks,calibration_final_sha256=hashlib.sha256((root/'FINAL.json').read_bytes()).hexdigest(),scope='Exploratory tuning on two seeds only; held-out settings frozen before validation')
    Path(out).open('x').write(json.dumps(result,indent=2)+'\n');print(json.dumps(result['selected']))


if __name__=='__main__':run(*sys.argv[1:])
