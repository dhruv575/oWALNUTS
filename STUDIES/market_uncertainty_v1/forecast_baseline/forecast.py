"""Exact conjugate baseline, not an SV model or a calibrated trading strategy."""
import argparse,json,math,hashlib
from pathlib import Path
import numpy as np
from scipy.stats import t
HORIZON=1800_000_000_000

def posterior(X,y,*,a0=3.,b0=.0002,prior_variance=100.):
 if any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in (a0,b0,prior_variance)):raise ValueError('Finite positive nonbool hyperparameters required')
 X=np.asarray(X,dtype=float);y=np.asarray(y,dtype=float)
 if X.ndim!=2 or y.shape!=(len(X),) or not np.isfinite(X).all() or not np.isfinite(y).all() or min(a0,b0,prior_variance)<=0:raise ValueError('Invalid conjugate input')
 p=X.shape[1];precision=np.eye(p)/prior_variance+X.T@X;V=np.linalg.solve(precision,np.eye(p));m=np.linalg.solve(precision,X.T@y)
 # Positive residual form avoids cancellation in y'y-m'precision*m.
 a=a0+len(y)/2;b=b0+.5*(np.sum((y-X@m)**2)+m@m/prior_variance)
 return dict(mean=m,covariance_factor=V,a=float(a),b=float(b),observations=len(y))

def distribution(post,x):
 x=np.asarray(x,dtype=float);m=post['mean'];V=post['covariance_factor'];a=post['a'];b=post['b']
 if x.shape!=m.shape or not np.isfinite(x).all():raise ValueError('Prediction shape/nonfinite')
 center=float(x@m);v=float(x@V@x);df=2*a;noise=b/a
 def interval(scale):return [center,center] if scale==0 else [float(t.ppf(q,df,loc=center,scale=scale)) for q in (.05,.95)]
 ps=math.sqrt(noise*(1+v));ms=math.sqrt(noise*v)
 return dict(mean=center,degrees_of_freedom=df,predictive_scale=ps,predictive_interval_90=interval(ps),conditional_mean_credible_interval_90=interval(ms),density_at_mean=float(t.pdf(center,df,loc=center,scale=ps)))

def fit_scaled(X,y):
 X=np.asarray(X,dtype=float);mu=X[:,1:].mean(axis=0);sd=X[:,1:].std(axis=0);sd=np.where(sd>1e-12,sd,1.)
 Z=X.copy();Z[:,1:]=(X[:,1:]-mu)/sd;post=posterior(Z,y)
 # beta_raw=A beta_standardized; exact coefficient transport.
 A=np.eye(X.shape[1]);A[0,1:]=-mu/sd;A[1:,1:]=np.diag(1/sd)
 return post,mu,sd,A

def feature(rows,index,flow):
 f=rows[index]['features'];anchor=f['anchor']
 if not anchor.get('available') or not anchor.get('midpoint',0)>0:return None,'missing_current_anchor'
 # Only past received anchors form the lagged return; no label is consulted.
 if index==0:return None,'missing_price_history'
 previous=rows[index-1]['features'];pa=previous['anchor']
 if f['origin_receipt_ns']-previous['origin_receipt_ns']!=HORIZON or not pa.get('available') or not pa.get('midpoint',0)>0:return None,'missing_regular_price_history'
 x=[1.,math.log(anchor['midpoint']/pa['midpoint'])]
 if flow:
  if f.get('flow_known') is not True:return None,'missing_flow'
  amount=f.get('total_amount');signed=f.get('signed_amount')
  if type(amount) not in (int,float) or type(signed) not in (int,float) or not math.isfinite(amount+signed) or amount<0 or abs(signed)>amount+1e-10:return None,'invalid_flow'
  x += [signed/amount if amount else 0.,math.log1p(amount)]
 return x,None

def forecast(dataset,origin,*,flow=True,minimum_history=20):
 if type(minimum_history)is not int or minimum_history<1:raise ValueError('Positive minimum history')
 rows=dataset['rows'];times=[r['features']['origin_receipt_ns'] for r in rows]
 if times!=sorted(set(times)):raise ValueError('Distinct ordered origins required')
 if any(r['label']['horizon_end_receipt_ns']-r['features']['origin_receipt_ns']!=HORIZON for r in rows):raise ValueError('Only30minute horizon supported')
 if origin not in times:raise ValueError('Origin absent')
 i=times.index(origin);x,reason=feature(rows,i,flow);result=dict(origin_receipt_ns=origin,model='price_plus_pooled_flow' if flow else 'price_history_only',status='no_forecast',qualified=False,horizon_ns=HORIZON,minimum_history=minimum_history)
 if reason:return dict(result,reason=reason,training_count=0)
 train=[]
 for j in range(i):
  label=rows[j]['label'];available=label.get('available_at_receipt_ns')
  if label.get('observed') is not True or type(available)is not int or available>origin:continue
  if available<label['horizon_end_receipt_ns']:raise ValueError('Label availability precedes horizon')
  xx,why=feature(rows,j,flow);yy=label.get('log_midpoint_return')
  if why or type(yy) not in (float,int) or not math.isfinite(yy):continue
  train.append((times[j],xx,yy))
 result.update(training_count=len(train),training_origins=[r[0] for r in train])
 if len(train)<minimum_history:return dict(result,reason='insufficient_mature_history')
 post,mu,sd,A=fit_scaled([r[1] for r in train],[r[2] for r in train]);z=np.array(x);z[1:]=(z[1:]-mu)/sd
 dist=distribution(post,z);rawm=A@post['mean'];rawV=A@post['covariance_factor']@A.T
 ci=np.array([t.ppf(q,2*post['a'],loc=rawm,scale=np.sqrt(post['b']/post['a']*np.diag(rawV))) for q in (.05,.95)]).T
 return dict(result,status='forecast',distribution=dist,scaling=dict(mean=mu.tolist(),sd=sd.tolist(),scope='past eligible training covariates only'),coefficient_mean_raw=rawm.tolist(),coefficient_credible_interval_90_raw=ci.tolist(),prior=dict(a0=3.,b0=.0002,conditional_coefficient_variance=100.,scope='zero-centered coefficients in each training-standardized design; outcome remains native log-return'),interpretation='Bayesian posterior predictive observation interval; parameter/conditional-mean credible intervals are separate. No frequentist coverage or causal-flow claim.')

def main():
 p=argparse.ArgumentParser();p.add_argument('--features',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--minimum-history',type=int,default=20);a=p.parse_args()
 raw=a.features.read_bytes();source=Path(__file__).read_bytes();data=json.loads(raw)
 results=[forecast(data,r['features']['origin_receipt_ns'],flow=flow,minimum_history=a.minimum_history) for r in data['rows'] for flow in (False,True)]
 if a.features.read_bytes()!=raw or Path(__file__).read_bytes()!=source:raise ValueError('Input/source changed during forecast')
 provenance=dict(features_path=str(a.features.resolve()),features_sha256=hashlib.sha256(raw).hexdigest(),source_sha256=hashlib.sha256(source).hexdigest(),minimum_history=a.minimum_history,numpy_version=np.__version__,scope='Input bytes bound, not independent validation of producer receipt/anchor semantics')
 with a.output.open('x') as f:json.dump(dict(scope='Chronological exact baseline only',qualified=False,provenance=provenance,outcomes=results),f,indent=2,allow_nan=False)
if __name__=='__main__':main()
