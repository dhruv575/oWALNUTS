from pathlib import Path
p=Path(__file__).resolve().parent;s=(p/'run_broad.py').read_text()
s=s.replace('from selector_full_shape import select','')
s=s.replace("root=Path(__file__).resolve().parent", "root=Path(__file__).resolve().parent\nchunk=int(sys.argv[1]);assert chunk in [1,2,3,4]")
s=s.replace("Path('/home/ubuntu/lanes/metric-blocks-recovery-20261030/evidence/broad01')", "Path('/home/ubuntu/lanes/metric-blocks-recovery-20261030/evidence')/root.name")
s=s.replace("root/'run_broad.py',root/'selector.py',root/'selector_full_shape.py',root/'BROAD-SCREEN.md'", "root/'run_hybrid.py',root/'hybrid_prepare.py',root/'hybrid_gate.py',root/'fisher_high_precision.py',root/'selector.py',root/'selector_full_shape.py',root/'HYBRID-VALIDATION.md',root.parent/'fisher04/mpmath-1.3.0-py3-none-any.whl'")
s=s.replace("folder=out/name;folder.mkdir();", "assert shutil.disk_usage('/').free>=1024**3,'root free-space floor'\n    folder=out/name;folder.mkdir();")
s=s.replace("r=execute([str(binary),str(folder/'INPUT.json'),str(folder/'RESULT.json')],str(root),180,", "cmd=([sys.executable,str(root/'hybrid_prepare.py')] if inp.get('prepare') else [str(binary)])+[str(folder/'INPUT.json'),str(folder/'RESULT.json')]\n    r=execute(cmd,str(root),180,")
s=s.replace('range(929100001,929100005)', 'range(929300001+4*(chunk-1),929300005+4*(chunk-1))')
start=s.index('        if pilot is None:');end=s.index("        persist('PROGRESS.json',rows)",s.index("        for arm in ['dense','auto']:",start))
s=s[:start]+'''        arms=['hybrid','v4','fisher','dense','auto']
        if pilot is None:
            rows.extend(dict(model=model,seed=seed,arm=a,passed=False,error='pilot_failed') for a in arms)
            persist('PROGRESS.json',rows);continue
        x=np.array(pilot['draws'])
        prep=job(prefix+'-fit',dict(prepare=True,pilot=str(out/(prefix+'-pilot')/'RESULT.json'),model=str(so),data=str(data)))
        for arm in arms:
            mode=arm;mass=None;extra_calls=0;extra_seconds=0;selection=None
            if arm in ['hybrid','v4','fisher']:
                if prep is None:
                    rows.append(dict(model=model,seed=seed,arm=arm,passed=False,error='fit_failed'));continue
                if arm=='hybrid':
                    branch=prep['branch'];extra_calls=prep['score_calls']+prep['probe_calls']
                    extra_seconds=sum(prep[k] for k in ['score_seconds','gate_seconds','fisher_seconds','probe_seconds'])
                    mass=prep['fisher_mass'] if branch=='fisher' else prep['v4_mass']
                    mode='auto' if branch=='auto' else 'fixed_dense';selection=dict(branch=branch,gate=prep['gate'],blocks=prep['selection']['blocks'])
                elif arm=='v4':
                    mode='fixed_dense' if prep['selection']['blocks'] else 'auto';mass=prep['v4_mass']
                    extra_calls=prep['probe_calls'];extra_seconds=prep['probe_seconds'];selection=prep['selection']
                else:
                    if prep['fisher_mass'] is None:
                        rows.append(dict(model=model,seed=seed,arm=arm,passed=False,error=prep['fisher_error']));continue
                    mode='fixed_dense';mass=prep['fisher_mass'];extra_calls=prep['score_calls']
                    extra_seconds=prep['score_seconds']+prep['fisher_seconds']
            args=dict(base,starts=x[:,-1,:].tolist(),seed=seed+100000,warmup=750,arm=mode)
            if mode=='fixed_dense':args['mass']=np.asarray(mass).ravel().tolist()
            r=job(prefix+'-'+arm,args)
            rows.append(analyze(r,seed,arm,pilot['target_calls']+extra_calls+(r or {}).get('target_calls',0),
                pilot['seconds']+extra_seconds+(r or {}).get('seconds',0),selection))
'''+s[end:]
(p/'run_hybrid.py').write_text(s)
