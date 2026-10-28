"""Descriptive leave-one-origin sensitivity, not a confidence interval."""
import hashlib,json,statistics,sys
from pathlib import Path

def analyze(root):
    rows=[];inputs={}
    for path in sorted(Path(root).glob('bounded-market-batch-*-20261028/SUMMARY.json')):
        raw=path.read_bytes();inputs[path.parent.name]=hashlib.sha256(raw).hexdigest();rows.extend(json.loads(raw))
    assert sorted(r['index'] for r in rows)==list(range(72))
    results=[]
    for cap in [.5,1.,2.]:
        selected=[r for r in rows if r['cap']==cap];assert len(selected)==24
        for baseline in ['rolling_t5','ewma_t5','nig_ar1']:
            values=[]
            for r in selected:
                c=next(c for c in r['comparisons'] if c['baseline']==baseline)
                assert c['qualified']
                values.append(dict(index=r['index'],month=r['month'],tick=r['tick'],score=c['total']))
            total=sum(v['score'] for v in values);ranked=sorted(values,key=lambda v:v['score'],reverse=True)
            loo=[(total-v['score'])/23 for v in values]
            results.append(dict(cap=cap,baseline=baseline,mean=total/24,median=statistics.median(v['score'] for v in values),best_origin=ranked[0],worst_origin=ranked[-1],mean_without_best=loo[values.index(ranked[0])],mean_without_top_two=(total-sum(v['score'] for v in ranked[:2]))/22,leave_one_out_min=min(loo),leave_one_out_max=max(loo),leave_one_out_nonpositive=sum(v<=0 for v in loo)))
    return dict(input_sha256=inputs,results=results,scope='Post hoc descriptive influence audit of all 24 origins per cap; no rows excluded from primary results and no selection of cap. Not a market-sampling uncertainty interval.')

if __name__=='__main__':Path(sys.argv[2]).write_text(json.dumps(analyze(sys.argv[1]),indent=2)+'\n')
