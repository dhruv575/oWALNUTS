"""Retrospective event-time flow/bar-close baseline; never receipt-time evidence."""
import bisect,hashlib,json,math
from pathlib import Path
from urllib.parse import urlparse,parse_qs
import numpy as np
from scipy.stats import t
import importlib.util
BASE=Path(__file__).resolve().parents[1]/'forecast_baseline/forecast.py'
spec=importlib.util.spec_from_file_location('historical_exact_baseline',BASE);baseline=importlib.util.module_from_spec(spec);spec.loader.exec_module(baseline)
HALF=1800000;WINDOW=900000
RECIPE=dict(schema='historical-baseline-recipe-v1',minimum_history=20,lookback=256,publication_lag_ms=0,a0=3.,b0=.0002,prior_variance=100.,initialization_end_ms=1789430400000,validation_end_ms=1790035200000,scope='Retrospective event-time pooled option amount and BTC-PERPETUAL traded bar-close return; not receipt midpoint, execution price, causal effect or future qualification')
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def finite(v):return type(v) in (int,float) and math.isfinite(v)

def verified_load(directory,*,protocol_path,collector_source):
    d=Path(directory);protocol=json.loads(Path(protocol_path).read_text());terminal=json.loads((d/'terminal.json').read_text());identity=json.loads((d/'launch-identity.json').read_text());bindings={}
    def read(p):
        p=Path(p);raw=p.read_bytes();bindings[str(p.resolve())]=hashlib.sha256(raw).hexdigest();return json.loads(raw)
    if terminal.get('status')!='completed' or terminal.get('complete') is not True:raise ValueError('Complete terminal acquisition required')
    if identity['source_sha256']!=digest(collector_source) or identity['source_sha256']!=digest(d/'source.py') or identity['protocol_sha256']!=digest(protocol_path):raise ValueError('Original collector/protocol identity differs')
    if read(d/'protocol.json')!=protocol or protocol['bar_publication_lag_ms']!=0:raise ValueError('Frozen protocol differs')
    for p in [protocol_path,collector_source,d/'source.py',d/'terminal.json',d/'launch-identity.json']:bindings[str(Path(p).resolve())]=digest(p)
    trades={};bar_rows=[];results={};total_bytes=0
    request_files=sorted(d.glob('request-*.json'))
    if len(list(d.glob('response-*.json')))!=terminal['requests'] or len(request_files)!=terminal['requests']:raise ValueError('Request denominator differs')
    for index,path in enumerate(request_files):
        req=read(path);rawpath=d/f'response-{index:05d}.json';raw=rawpath.read_bytes();bindings[str(rawpath.resolve())]=hashlib.sha256(raw).hexdigest();total_bytes+=len(raw)
        if req.get('index')!=index or req.get('status')!='completed' or req.get('http_status')!=200 or req['sha256']!=bindings[str(rawpath.resolve())] or req['bytes']!=len(raw):raise ValueError('Raw response identity/status mismatch')
        response=json.loads(raw)
        if 'error' in response:raise ValueError('RPC error')
        result=response['result'];results[index]=(req,result);url=urlparse(req['url']);query=parse_qs(url.query)
        if url.scheme!='https' or url.hostname!='history.deribit.com':raise ValueError('Unexpected historical source')
        if url.path.endswith('get_last_trades_by_currency_and_time'):
            if query.get('currency')!=['BTC'] or query.get('kind')!=['option']:raise ValueError('Wrong trade market')
            lo=int(query['start_timestamp'][0]);hi=int(query['end_timestamp'][0])
            if type(result.get('has_more')) is not bool:raise ValueError('Missing completeness flag')
            for row in result['trades']:
                name=row.get('instrument_name','');stamp=row.get('timestamp');amount=row.get('amount')
                if type(stamp)is not int or not lo<=stamp<=hi or not name.startswith('BTC-') or not name.endswith(('-C','-P')) or row.get('direction') not in ('buy','sell') or not finite(amount) or amount<=0:raise ValueError('Trade domain mismatch')
                key=row['trade_id']
                if key in trades and trades[key]!=row:raise ValueError('Conflicting duplicate raw trade')
                trades[key]=row
        elif url.path.endswith('get_tradingview_chart_data'):
            if query.get('instrument_name')!=['BTC-PERPETUAL'] or query.get('resolution')!=['30'] or result.get('status')!='ok':raise ValueError('Wrong bar contract')
            lo=int(query['start_timestamp'][0]);hi=int(query['end_timestamp'][0]);ticks=list(range(lo,hi+1,HALF))
            if result['ticks']!=ticks:raise ValueError('Raw bar gap')
            for i,stamp in enumerate(ticks):bar_rows.append(dict(open_ms=stamp,close_available_ms=stamp+HALF,**{k:result[k][i] for k in ['open','high','low','close','volume']}))
        else:raise ValueError('Unexpected API method')
    if total_bytes!=terminal['response_bytes']:raise ValueError('Response byte denominator mismatch')
    leaves=read(d/'completed-trade-leaves.json');cursor=protocol['start_ms']
    for leaf in sorted(leaves,key=lambda x:x['start_ms']):
        req,res=results[leaf['request_index']];qs=parse_qs(urlparse(req['url']).query)
        if leaf['start_ms']!=cursor or res.get('has_more') is not False or len(res['trades'])!=leaf['count'] or int(qs['start_timestamp'][0])!=leaf['start_ms'] or int(qs['end_timestamp'][0])!=leaf['end_ms']:raise ValueError('Unproven leaf coverage')
        cursor=leaf['end_ms']+1
    if cursor!=protocol['end_ms_exclusive']:raise ValueError('Trade coverage gap')
    raw=(d/'trades.jsonl').read_bytes();bindings[str((d/'trades.jsonl').resolve())]=hashlib.sha256(raw).hexdigest();saved=[json.loads(x) for x in raw.splitlines()];keys=[x['trade_id'] for x in saved]
    if len(set(keys))!=len(keys) or {x['trade_id']:x for x in saved}!=trades or len(saved)!=terminal['trade_count']:raise ValueError('Final trade file differs from raw responses')
    bars=read(d/'bars.json')
    if bars!=bar_rows or len(bars)!=terminal['bar_count']:raise ValueError('Final bars differ from raw responses')
    rows=convert(saved,bars,protocol['start_ms'],protocol['end_ms_exclusive'])
    if any(digest(p)!=h for p,h in bindings.items()):raise ValueError('Acquisition changed during admission')
    return dict(rows=rows,bindings=bindings,protocol=protocol,scope=RECIPE['scope'])

def convert(trades,bars,start,end):
    if [b['open_ms'] for b in bars]!=list(range(start,end,HALF)):raise ValueError('Duplicate/missing/out-of-order scheduled bars')
    for b in bars:
        if b['close_available_ms']!=b['open_ms']+HALF or not finite(b['close']) or b['close']<=0:raise ValueError('Bar timing/price invalid')
    for r in trades:
        if type(r.get('timestamp')) is not int or not start<=r['timestamp']<end or not finite(r.get('amount')) or r['amount']<=0 or r.get('direction') not in ('buy','sell'):raise ValueError('Invalid final trade domain')
    ids=[r['trade_id'] for r in trades]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate final trade ID')
    trades=sorted(trades,key=lambda x:x['timestamp']);stamps=[x['timestamp'] for x in trades];rows=[]
    for i,b in enumerate(bars):
        origin=b['close_available_ms'];lo=bisect.bisect_left(stamps,origin-WINDOW);hi=bisect.bisect_left(stamps,origin);window=trades[lo:hi]
        total=sum(x['amount'] for x in window);signed=sum(x['amount']*(1 if x['direction']=='buy' else -1) for x in window)
        rows.append(dict(origin_ms=origin,bar_close=b['close'],lag_return=None if i==0 else math.log(b['close']/bars[i-1]['close']),flow_known=True,flow_count=len(window),total_amount=total,signed_amount=signed,log_bar_close_return=None if i+1==len(bars) else math.log(bars[i+1]['close']/b['close']),label_available_ms=None if i+1==len(bars) else origin+HALF))
    return rows

def forecast(rows,index,flow,*,minimum_history=20,lookback=256):
    current=rows[index];origin=current['origin_ms'];result=dict(origin_ms=origin,model='price_plus_flow' if flow else 'price_only',status='no_forecast',qualified=False)
    if current['lag_return'] is None:return dict(result,reason='missing_lag',training_count=0)
    def design(r):
        x=[1.,r['lag_return']]
        if flow:x.extend([r['signed_amount']/r['total_amount'] if r['total_amount'] else 0.,math.log1p(r['total_amount'])])
        return x
    eligible=[r for r in rows[max(0,index-lookback):index] if r['lag_return'] is not None and r['label_available_ms'] is not None and r['label_available_ms']<=origin]
    result.update(training_count=len(eligible),training_origins=[r['origin_ms'] for r in eligible])
    if len(eligible)<minimum_history:return dict(result,reason='insufficient_mature_history')
    X=np.asarray([design(r) for r in eligible]);y=np.asarray([r['log_bar_close_return'] for r in eligible]);mu=X[:,1:].mean(0);sd=X[:,1:].std(0);sd=np.where(sd>1e-12,sd,1.);X[:,1:]=(X[:,1:]-mu)/sd;x=np.asarray(design(current));x[1:]=(x[1:]-mu)/sd
    post=baseline.posterior(X,y,a0=3.,b0=.0002,prior_variance=100.);dist=baseline.distribution(post,x)
    return dict(result,status='forecast',distribution=dist,scaling=dict(mean=mu.tolist(),sd=sd.tolist()),publication_lag_ms=0)

def evaluate(dataset):
    rows=dataset['rows'];out=[]
    for i,r in enumerate(rows):
        phase='initialization' if r['origin_ms']<RECIPE['initialization_end_ms'] else ('validation' if r['origin_ms']<RECIPE['validation_end_ms'] else 'exploratory_evaluation')
        for flow in [False,True]:
            result=forecast(rows,i,flow);result['phase']=phase;result['observed_label']=r['log_bar_close_return']
            if result['status']=='forecast' and r['log_bar_close_return'] is not None:
                d=result['distribution'];lo,hi=d['predictive_interval_90'];y=r['log_bar_close_return'];result['scores']=dict(covered=lo<=y<=hi,interval_score=hi-lo+20*max(lo-y,0)+20*max(y-hi,0),log_score=float(t.logpdf(y,d['degrees_of_freedom'],loc=d['mean'],scale=d['predictive_scale'])))
            else:result['scores']=None
            out.append(result)
    return dict(qualified=False,recipe=RECIPE,outcomes=out,scope=RECIPE['scope'])

def main():
    import argparse,time
    parser=argparse.ArgumentParser();parser.add_argument('--acquisition',type=Path,required=True);parser.add_argument('--protocol',type=Path,required=True);parser.add_argument('--collector-source',type=Path,required=True);parser.add_argument('--recipe',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    recipe=json.loads(args.recipe.read_text())
    if recipe['recipe']!=RECIPE or recipe['status']!='frozen_before_final_segment_fit':raise ValueError('Prospective recipe required')
    for path,sha in recipe['source_bindings'].items():
        if digest(path)!=sha:raise ValueError('Recipe source drift')
    started=time.perf_counter();args.out.mkdir(exist_ok=False)
    try:
        dataset=verified_load(args.acquisition,protocol_path=args.protocol,collector_source=args.collector_source)
        (args.out/'features.json').write_text(json.dumps(dataset,indent=2,allow_nan=False));result=evaluate(dataset)
        if any(digest(p)!=h for p,h in {**dataset['bindings'],**recipe['source_bindings']}.items()):raise ValueError('Input/source changed during evaluation')
        result.update(status='completed',recipe_sha256=digest(args.recipe),provenance=dataset['bindings'],elapsed_seconds=time.perf_counter()-started)
        (args.out/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False))
    except Exception as exc:
        (args.out/'failure.json').write_text(json.dumps(dict(status='failed',error=repr(exc),elapsed_seconds=time.perf_counter()-started),indent=2));raise
if __name__=='__main__':main()
