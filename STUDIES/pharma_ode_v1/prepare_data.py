import csv,json,re,math
from pathlib import Path

root=Path(__file__).resolve().parent;out=root/'data';out.mkdir(exist_ok=False)
text=(root/'source_data/stan-public.data.R').read_text()
times=[float(x) for x in re.search(r'times\s*<-\s*c\((.*?)\)',text,re.S).group(1).split(',')]
conc=[float(x) for x in re.search(r'\nC\s*<-\s*c\((.*?)\)',text,re.S).group(1).split(',')]
cases={}
def save(name,d,meta):
    d.update(tol=1e-8,solver=0);(out/f'{name}.json').write_text(json.dumps(d,indent=2)+'\n');cases[name]=meta
d=dict(P=4,N=len(times),times=times,concentration=conc,Npred=len(times),pred_times=times,dose=30.,fixed_v=2.,c0=0.,infer_v=0,linear=0,half_cauchy=1,prior_mean=[0.,0.,0.,math.log(.1)],prior_sd=[1.]*4)
save('stan_public',d,dict(kind='public computational benchmark; clinical provenance unverified',holdout_times=[],holdout_concentration=[],threshold=max(conc)/2))
data=list(csv.DictReader((root/'source_data/Theoph.csv').open()))
for subject in ('1','2','3'):
    g=sorted([r for r in data if r['Subject']==subject],key=lambda r:float(r['Time']))
    baseline=float(g[0]['conc']);assert float(g[0]['Time'])==0
    post=g[1:];train=post[:-2];test=post[-2:];weight=float(g[0]['Wt']);dose=weight*float(g[0]['Dose'])
    common=dict(N=len(train),times=[float(x['Time']) for x in train],concentration=[float(x['conc']) for x in train],Npred=len(post),pred_times=[float(x['Time']) for x in post],dose=dose,fixed_v=1.,c0=baseline,infer_v=1,half_cauchy=0)
    meta=dict(kind='observed theophylline subject; individual conditional model',subject=int(subject),baseline_conditioned=baseline,weight_kg=weight,holdout_times=[float(x['Time']) for x in test],holdout_concentration=[float(x['conc']) for x in test],threshold=max(common['concentration'])/2)
    mm=dict(common,P=5,linear=0,prior_mean=[0.,math.log(5.),math.log(dose/24),math.log(.5*weight),math.log(.2)],prior_sd=[1.2,1.5,1.5,.7,.7])
    lin=dict(common,P=4,linear=1,prior_mean=[0.,math.log(.1),math.log(.5*weight),math.log(.2)],prior_sd=[1.2,1.2,.7,.7])
    save('theoph_'+subject,mm,meta);save('linear_'+subject,lin,meta)
(out/'CASES.json').write_text(json.dumps(cases,indent=2)+'\n')
print(list(cases))
