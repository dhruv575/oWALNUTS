"""Causal receipt-feature admission for SV; no fitting or market qualification.

Mean design: intercept, optionally signed/total flow and log1p(raw amount).
Scale design: optionally absolute imbalance and log1p(raw amount). Priors apply
in training-standardized coordinates: scaling changes their physical meaning.
Returns are never standardized. Unknown scale forcing causes no-fit, not zero
fill or latent-grid compression. Input producer provenance is not revalidated.
"""
import math
import numpy as np
HORIZON=1800_000_000_000
ARMS=('neither','mean','scale','both')


def build(dataset, origin, *, ablation, minimum_history, lookback):
    if type(origin)is not int or ablation not in ARMS or any(type(v)is not int or v<1 for v in (minimum_history,lookback)):
        raise ValueError('Explicit origin, ablation, positive history and lookback required')
    rows=dataset['rows'];times=[r['features']['origin_receipt_ns'] for r in rows]
    if any(type(t)is not int for t in times) or times!=sorted(set(times)) or origin not in times:
        raise ValueError('Distinct ordered origins including forecast origin required')
    result=dict(status='no_fit',qualified=False,ablation=ablation,origin_receipt_ns=origin,minimum_history=minimum_history,lookback=lookback)
    idx=times.index(origin);start=max(0,idx-lookback);selected=rows[start:idx];current=rows[idx]
    anchor=current['features'].get('anchor',{})
    midpoint=anchor.get('midpoint')
    if anchor.get('available') is not True or type(midpoint) not in (int,float) or not math.isfinite(midpoint) or midpoint<=0:
        return dict(result,reason='missing_forecast_anchor')
    ts=times[start:idx+1]
    if any(b-a!=HORIZON for a,b in zip(ts,ts[1:])):
        return dict(result,reason='missing_scheduled_grid_rows')
    if not selected:return dict(result,reason='insufficient_mature_history',training_count=0)
    meanflow=ablation in ('mean','both');scaleflow=ablation in ('scale','both')
    def design(row):
        f=row['features'];known=f.get('flow_known') is True
        amount,signed=f.get('total_amount'),f.get('signed_amount')
        valid=known and all(type(v)in(int,float) and math.isfinite(v) for v in (amount,signed))
        valid=valid and amount>=0 and abs(signed)<=amount+1e-10
        if not valid:return [1.]+([float('nan')]*2 if meanflow else []),([float('nan')]*2 if scaleflow else [])
        imbalance=signed/amount if amount else 0.
        return [1.]+([imbalance,math.log1p(amount)] if meanflow else []),([abs(imbalance),math.log1p(amount)] if scaleflow else [])
    X=[];W=[];y=[];mask=[]
    for row in selected:
        f,label=row['features'],row['label'];end=f['origin_receipt_ns']+HORIZON
        if label['horizon_end_receipt_ns']!=end:raise ValueError('Only fixed 30-minute labels supported')
        available=label.get('available_at_receipt_ns');observed=label.get('observed') is True
        if observed and (type(available)is not int or available<end):raise ValueError('Invalid label availability')
        eligible=observed and available<=origin and end<=origin
        value=label.get('log_midpoint_return') if eligible else None
        if eligible and (type(value)not in(int,float) or not math.isfinite(value)):raise ValueError('Nonfinite observed return')
        x,w=design(row);eligible=eligible and bool(np.isfinite(x).all())
        X.append(x);W.append(w);y.append(value if eligible else float('nan'));mask.append(eligible)
    xn,wn=design(current) # Never inspect current or future labels.
    X=np.asarray(X);W=np.asarray(W).reshape(len(selected),-1);mask=np.asarray(mask,dtype=bool)
    if scaleflow and not np.isfinite(W).all():return dict(result,reason='unknown_scale_covariates',training_count=int(mask.sum()))
    if not np.isfinite(xn).all() or not np.isfinite(wn).all():return dict(result,reason='unknown_forecast_covariates',training_count=int(mask.sum()))
    if mask.sum()<minimum_history:return dict(result,reason='insufficient_mature_history',training_count=int(mask.sum()))
    def scale(a,next_a,skip):
        mu=a[mask,skip:].mean(axis=0);sd=a[mask,skip:].std(axis=0);sd=np.where(sd>1e-12,sd,1.)
        out=a.copy();out[:,skip:]=(a[:,skip:]-mu)/sd
        nxt=np.asarray(next_a,dtype=float).copy();nxt[skip:]=(nxt[skip:]-mu)/sd
        return out,nxt,dict(mean=mu.tolist(),sd=sd.tolist())
    X,xn,sx=scale(X,xn,1);W,wn,sw=scale(W,wn,0)
    return dict(result,status='ready',training_count=int(mask.sum()),training_origins=ts[:-1],
                data=dict(y=np.asarray(y),x=X,w=W,observed=mask),forecast=dict(x_next=xn,w_next=wn),
                scaling=dict(x=sx,w=sw,scope='Mature eligible training rows only; prior is on standardized coefficients; native return outcome unchanged'))
