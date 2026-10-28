"""Post-seal arithmetic audit of frozen outputs; no scoring, bootstrap or RNG."""
import argparse,hashlib,json,math
from pathlib import Path

MONTHS=(('2025-12',1488),('2026-01',1488),('2026-02',1344))
ARMS=('candidate','rolling_t5','ewma_t5')
SIDES=('long','short')

def read(path):
    raw=Path(path).read_bytes();return json.loads(raw),hashlib.sha256(raw).hexdigest()

def equal(actual,expected):
    if not isinstance(expected,(int,float)) or not math.isfinite(expected) or not math.isclose(actual,expected,rel_tol=1e-12,abs_tol=1e-15):raise ValueError('Frozen summary arithmetic mismatch')

def audit(root):
    root=Path(root);out=dict(scope='Frozen-result arithmetic only; no new inference',months={},comparisons=[],references=[])
    for month,n in MONTHS:
        summary,sh=read(root/'reports'/month/'summary.json');rows,lh=read(root/'reports'/month/'ledger.json')
        if len(rows)!=n or [(r['month'],r['tick']) for r in rows]!=[(month,t) for t in range(1,n+1)]:raise ValueError('Planned origin identity mismatch')
        counts={arm:sum(r['arms'][arm].get('status')=='ok' for r in rows) for arm in ARMS}
        out['months'][month]=dict(planned_origins=n,available=counts,summary_sha256=sh,ledger_sha256=lh,arms=summary['arms'])
        for arm in ARMS:
            if counts[arm]!=summary['arms'][arm]['available']:raise ValueError('Availability mismatch')
            if counts[arm]==n:
                for side in SIDES:
                    scored=[r['arms'][arm]['risk'][side] for r in rows]
                    equal(sum(x['pinball'] for x in scored)/n,summary['arms'][arm]['tails'][side]['mean_pinball'])
                    equal(sum(x['exceedance'] for x in scored)/n,summary['arms'][arm]['tails'][side]['exceedance_rate'])
        for arm in ARMS[1:]:
            for side in SIDES:
                key=arm+'_'+side;s=summary['comparisons'][key]
                paired=[r for r in rows if all(r['arms'][a].get('status')=='ok' for a in ('candidate',arm))]
                if len(paired)!=s['available']:raise ValueError('Paired denominator mismatch')
                record=dict(month=month,baseline=arm,side=side,planned=n,available=len(paired),frozen=s)
                if len(paired)==n:
                    loss=sum(r['arms'][arm]['risk'][side]['pinball']-r['arms']['candidate']['risk'][side]['pinball'] for r in paired)/n
                    exc=sum(r['arms'][arm]['risk'][side]['exceedance']-r['arms']['candidate']['risk'][side]['exceedance'] for r in paired)/n
                    equal(loss,s['mean_advantage']);equal(exc,s['mean_exceedance_difference']);denominator=summary['arms'][arm]['tails'][side]['mean_pinball'];equal(loss/denominator,s['relative_mean_loss_reduction']) if denominator>0 else None;record.update(recomputed_mean_advantage=loss,recomputed_exceedance_difference=exc)
                elif s['mean_advantage']is not None:raise ValueError('Incomplete panel has full mean')
                out['comparisons'].append(record)
        out['references'].extend(summary['references'])
    if len(out['comparisons'])!=12 or len(out['references'])!=24:raise ValueError('Planned comparison/reference count changed')
    out['planned_origins']=4320;out['planned_arm_origins']=12960;return out

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--out',required=True);a=p.parse_args();result=audit(a.root)
    with Path(a.out).open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
if __name__=='__main__':main()
