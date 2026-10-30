from pathlib import Path
p=Path(__file__).resolve().parent;s=(p/'run_hybrid.py').read_text()
s=s.replace('chunk in [1,2,3,4]','chunk in range(1,9)')
s=s.replace("root/'run_hybrid.py',root/'hybrid_prepare.py',root/'hybrid_gate.py'", "root/'run_scaled.py',root/'scaled_worker.py',root/'scaled_policy.py',root/'hybrid_gate.py'")
s=s.replace("root/'HYBRID-VALIDATION.md'","root/'SCALED-VALIDATION.md'")
s=s.replace("root/'hybrid_prepare.py')] if inp.get('prepare')", "root/'scaled_worker.py')] if inp.get('policy')")
s=s.replace('range(929300001+4*(chunk-1),929300005+4*(chunk-1))','range(929500001+2*(chunk-1),929500003+2*(chunk-1))')
s=s.replace("begin=time.monotonic()", "port=json.loads((root.parent/'scaledport01/SUMMARY.json').read_text());assert port['passed']\nfor name in ['scaled_policy.py','scaled_worker.py','hybrid_gate.py','selector.py','selector_full_shape.py','fisher_high_precision.py']:\n    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==port['sources'][name]\nbegin=time.monotonic()")
start=s.index("        arms=['hybrid'");end=s.index("        persist('PROGRESS.json',rows)",s.index("        for arm in arms:",start))
s=s[:start]+'''        arms=['scaled','hybrid','v4','fisher','dense','auto'];rotation=(seed-929500001)%6;arms=arms[rotation:]+arms[:rotation]
        if pilot is None:
            rows.extend(dict(model=model,seed=seed,arm=a,passed=False,error='pilot_failed') for a in arms)
            persist('PROGRESS.json',rows);continue
        x=np.array(pilot['draws']);pilotpath=out/(prefix+'-pilot')/'RESULT.json'
        pilot_elapsed=json.loads((pilotpath.parent/'SUPERVISION.json').read_text())['elapsed_seconds']
        for arm in arms:
            args=dict(base,starts=x[:,-1,:].tolist(),seed=seed+100000,warmup=750)
            r=job(prefix+'-'+arm,dict(policy=arm,pilot=str(pilotpath),sampler=args,binary=str(binary)))
            folder=out/(prefix+'-'+arm);sup=json.loads((folder/'SUPERVISION.json').read_text())
            if r is None:
                rows.append(dict(model=model,seed=seed,arm=arm,passed=False,error='policy_job_failed'));continue
            policy=json.loads((folder/'POLICY.json').read_text())
            expected=400+64*d if arm in ['scaled','hybrid'] else (400 if arm=='fisher' else (64*d if arm=='v4' else 0))
            assert policy['calls']==expected
            selection={k:policy[k] for k in ['branch','gate','selection','scaled_selection'] if k in policy}
            rr=analyze(r,seed,arm,pilot['target_calls']+policy['calls']+r['target_calls'],pilot_elapsed+sup['elapsed_seconds'],selection)
            rr.update(pilot_invocation_seconds=pilot_elapsed,policy_invocation_seconds=sup['elapsed_seconds'],
                timing_scope='Supervisor invocation-through-output; shared pilot charged; common diagnostics/controller IO excluded')
            rows.append(rr)
'''+s[end:]
(p/'run_scaled.py').write_text(s)
