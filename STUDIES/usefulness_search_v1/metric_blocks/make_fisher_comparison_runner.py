"""Generate the supplemental runner from reviewed broad-screen scaffolding."""
from pathlib import Path
p=Path(__file__).resolve().parent;s=(p/'run_broad.py').read_text()
s=s.replace('from selector_full_shape import select','')
s=s.replace('evidence/broad01','evidence/fishercompare01')
s=s.replace("root/'run_broad.py',root/'selector.py',root/'selector_full_shape.py',root/'BROAD-SCREEN.md'", "root/'run_fisher_comparison.py',root/'fisher_prepare.py',root/'fisher_high_precision.py',root/'FISHER-COMPARISON.md',root.parent/'broad01/SUMMARY.json'")
s=s.replace("r=execute([str(binary),str(folder/'INPUT.json'),str(folder/'RESULT.json')],str(root),180,", "cmd=([sys.executable,str(root/'fisher_prepare.py')] if inp.get('prepare') else [str(binary)])+[str(folder/'INPUT.json'),str(folder/'RESULT.json')]\n    r=execute(cmd,str(root),180,")
start=s.index("        pilot=job(prefix+'-pilot'")
end=s.index("        persist('PROGRESS.json',rows)",s.index("        for arm in ['dense','auto']:",start))
s=s[:start]+'''        pilotpath=root.parent/'broad01/runs'/(prefix+'-pilot')/'RESULT.json'
        record(pilotpath);pilot=json.loads(pilotpath.read_text());x=np.array(pilot['draws'])
        prepared=job(prefix+'-fit',dict(prepare=True,pilot=str(pilotpath),model=str(so),data=str(data)))
        if prepared is None:
            rows.append(dict(model=model,seed=seed,arm='fisher',passed=False,error='fit_failed'))
        else:
            r=job(prefix+'-fisher',dict(base,starts=x[:,-1,:].tolist(),seed=seed+100000,warmup=750,
                arm='fixed_dense',mass=np.array(prepared['mass']).ravel().tolist()))
            rows.append(analyze(r,seed,'fisher',pilot['target_calls']+prepared['target_calls']+(r or {}).get('target_calls',0),
                pilot['seconds']+prepared['seconds']+(r or {}).get('seconds',0)))
'''+s[end:]
(p/'run_fisher_comparison.py').write_text(s)
