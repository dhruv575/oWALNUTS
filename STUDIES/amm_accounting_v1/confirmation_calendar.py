"""Outcome-free confirmation schedule; seed reservations need separate global audit."""
from datetime import datetime,timedelta,timezone
import json,sys
from pathlib import Path

def schedule():
    cells=[]
    for month,n in [('2025-09',1440),('2025-10',1488)]:
        start=datetime.fromisoformat(month+'-01').replace(tzinfo=timezone.utc)
        for t in range(1,n+1):
            origin=start+timedelta(minutes=30*(t-1))
            for cap in ([1.,.5,2.] if (t-1)%48==0 else [1.]):
                index=len(cells);base=398201000+16*index
                cells.append(dict(index=index,month=month,tick=t,cap=cap,primary=cap==1.,origin_ms=int(origin.timestamp()*1000),label_available_ms=int((origin+timedelta(minutes=30)).timestamp()*1000),window_start=t,window_stop=250+t,label_index=250+t,nuts_seed=base,stan_data_seed=base+1,walnuts_seed=base+4))
    assert len(cells)==3050
    return dict(status='pre_acquisition_schedule_pending_global_seed_audit',cells=cells,seed_reservation=[398201000,398201000+16*len(cells)-1],bootstrap_seed_reservation=[398300000,398300005],bootstrap_order='September blocks96/48/336, then October blocks96/48/336; paired columns share resamples')

if __name__=='__main__':Path(sys.argv[1]).write_text(json.dumps(schedule(),indent=2)+'\n')
