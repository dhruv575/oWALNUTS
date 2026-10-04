"""Independent read-only candidate prelaunch review; never freezes or launches.

Explicit input paths avoid guessing an evolving preparation schema. Missing
protocol fields fail closed. This reviews readiness, not statistical truth.
"""
import argparse
import hashlib
import json
import math
import re
import random
from pathlib import Path

# Target is read from independently pinned bank below; no caller-supplied scales.
NAMES = [f'{name}_{p}' for name in ('beta_bar','tau','mu_h','sigma_h','h_terminal','observed_group0_h1') for p in (.05,.95)]

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()

def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def key(path): return str(Path(path).resolve()).casefold()

def review(args):
    checks=[]
    def check(name, predicate, detail=None):
        checks.append(dict(name=name,passed=bool(predicate),detail=detail))
    def bindings(values,label):
        result={}
        for path,digest in values.items():
            try: actual=sha(path)
            except (OSError,ValueError) as e:
                check(label+':'+path,False,str(e)); continue
            check(label+':'+path,actual==digest)
            result[key(path)]=digest
        return result
    try:
        import numpy as np
        plan=read(args.plan); protocol=read(args.protocol); pairs=read(args.pairs)
        counts=np.load(args.counts,allow_pickle=False); indices=np.load(args.indices,allow_pickle=False)
        pin=read(args.bank_pin); audit=read(args.seed_audit)
        source=bindings(plan['sources'],'source')
        source.update(bindings(protocol.get('sources',{}),'protocol_source'))
        bound=bindings(plan['bindings'],'input')
        bound.update(bindings(protocol['bindings'],'protocol'))
        for path in (args.pairs,args.counts,args.indices,args.bank_pin,args.seed_audit):
            check('prospectively_bound:'+str(path),bound.get(key(path))==sha(path))
        check('plan_binds_prefit_intent',key(plan['decision_intent'])==key(args.protocol) and bound.get(key(args.protocol))==sha(args.protocol))
        if Path(args.plan).with_suffix('.sha256').exists():
            check('plan_sidecar',Path(args.plan).with_suffix('.sha256').read_text().strip()==sha(args.plan))
        check('no_execution_started',not (Path(args.plan).parent/'execution-started.json').exists())
        cells=plan['cells']; ids=[c['id'] for c in cells]
        check('72_unique_ids',len(cells)==72 and len(set(ids))==72)
        expected_pairs=[f'pair{i:02}' for i in range(36)]
        check('36_exact_pair_ids',[p['id'] for p in pairs]==expected_pairs)
        expected_order=[]; initial=[]; independent=[]; starts=[]
        lookup={c['id']:c for c in cells}
        for i,pair in enumerate(pairs):
            order=('public','reference') if i%2==0 else ('reference','public')
            expected_order.extend(pair[a] for a in order)
            rows=[lookup[pair[a]] for a in ('public','reference')]
            check('paired_identity:'+pair['id'],all(c['backend']==a and c['pair_id']==pair['id'] for c,a in zip(rows,('public','reference'))))
            check('shared_initialization:'+pair['id'],rows[0]['initialization_seed']==rows[1]['initialization_seed'])
            initial.append(rows[0]['initialization_seed'])
            matrices=[]
            for c in rows:
                independent.extend([c['sampler_seed'],c['prediction_seed']])
                check('prediction_rule:'+c['id'],c['prediction_seed']==c['sampler_seed']+130000)
                fixture=read(c['fixture']); matrix=np.asarray(fixture['data']['initial_positions'])
                check('physical_start_shape:'+c['id'],matrix.shape==(4,1012) and np.isfinite(matrix).all())
                check('fixture_hash:'+c['id'],sha(c['fixture'])==c['fixture_sha256'])
                matrices.append(matrix)
                cmd=c['command']
                def option(flag):
                    return cmd[cmd.index(flag)+1] if flag in cmd else None
                check('actual_worker_policy:'+c['id'],option('--cpus')=='0' and float(option('--timeout'))==1800 and option('--warmup')=='1000' and option('--chains')=='4' and option('--seed')==str(c['sampler_seed']) and cmd[cmd.index('--tiers')+1:cmd.index('--tiers')+5]==['1000','2000','4000','8000'])
                check('actual_recipe:'+c['id'],(option('--coordinates')=='mixed_slopes' and option('--block-size')=='32') if c['backend']=='public' else (option('--implementation')=='associative' and option('--target-accept')=='0.9'))
                for role in ('worker_directory','controller_status','hardware','started','exit','log'):
                    check('no_prior_activity:'+c['id']+':'+role,not Path(c[role]).exists())
            check('identical_physical_starts:'+pair['id'],np.array_equal(*matrices))
            starts.append(hashlib.sha256(matrices[0].tobytes()).hexdigest())
        check('adjacent_alternating_execution',ids==expected_order)
        streams=initial+independent
        check('180_distinct_streams',len(streams)==180 and len(set(streams))==180 and all(type(s)is int and 0<=s<2**32 for s in streams))
        check('36_distinct_start_matrices',len(set(starts))==36)
        check('count_matrix',counts.shape==(40000,36) and counts.dtype.kind in 'iu' and (counts>=0).all() and (counts.astype('int64').sum(axis=1)==36).all())
        check('shared_bank_indices',indices.shape==(40000,) and indices.dtype.kind in 'iu' and (indices>=0).all() and (indices<30000).all())
        decision=read(plan['decision_intent'])
        check('comparison_seed_role',decision['resampling_seed']==audit['comparison_seed'] and decision['resampling_seed'] not in streams)
        rng=random.Random(decision['resampling_seed']); mismatch=[]
        for row in range(40000):
            expected=[0]*36
            for _ in range(36): expected[rng.randrange(36)]+=1
            expected_index=rng.randrange(30000)
            if counts[row].tolist()!=expected or int(indices[row])!=expected_index:
                if len(mismatch)<10: mismatch.append(row)
        check('exact_declared_resampling_sequence',not mismatch,mismatch)
        check('fit_seed_audit',audit['status']=='passed' and audit['hits']==[] and set(audit['seeds'])==set(streams))
        evidence=audit['supplemental_evidence']; check('historical_supplement_hash',sha(evidence['path'])==evidence['sha256'])
        broad=read(evidence['path'])
        check('historical_scope',broad['status']=='passed' and broad['hits']==[] and set(streams)<=set(broad['seeds']) and bool(broad['inventory_files']))
        bindings(broad['inventory_files'],'historical_inventory')
        hits=[]
        sought=set(streams)|{audit['comparison_seed']}
        token=re.compile(r'(?<![\w.])\d[\d_]*(?![\w.])')
        for path in broad['inventory_files']:
            raw=Path(path).read_bytes()
            text=raw.decode('utf-16' if raw[:2] in (b'\xff\xfe',b'\xfe\xff') else 'utf-8-sig')
            found={int(m.group().replace('_','')) for m in token.finditer(text)} & sought
            if found: hits.append(dict(path=path,seeds=sorted(found)))
        check('independent_historical_literal_scan',not hits,hits)
        for role in ('prior_reserved','prior_inventory'):
            prior=broad[role]
            check('prior_seed_evidence:'+role,sha(prior['path'])==prior['sha256'])
        prior=read(broad['prior_reserved']['path'])
        reserved=prior.get('reserved_seeds',prior.get('reserved'))
        check('explicit_historical_reserved_list',isinstance(reserved,list))
        if isinstance(reserved,list): check('reserved_stream_exclusion',not sought.intersection(reserved))
        bankbindings=bindings(pin['bindings'],'bank')
        for role in ('intent','bank','status','audit','analysis','audit_provenance','analysis_plan','grid','manifest'):
            check('bank_role:'+role,bankbindings.get(key(pin[role]))==sha(pin[role]))
        bank=read(pin['bank']); intent=read(pin['intent'])
        check('exact_bank_target',plan['bank_posterior_sha256']==pin['target_sha256']==bank['target_sha256']==intent['posterior_sha256'])
        check('exact_endpoint_family',set(bank['endpoints'])==set(NAMES) and set(intent['endpoints'])==set(NAMES))
        check('bank_resolved',bank['status']=='numerically_resolved_under_declared_checks' and bank['expected_fits']==bank['recorded_fits']==64 and not bank['reasons'])
        check('30000_joint_bank_vectors',len(bank['joint_bootstrap_endpoints'])==30000)
        for name in NAMES:
            ep=bank['endpoints'][name]
            check('positive_fixed_width:'+name,type(ep['W_low']) in (int,float) and math.isfinite(ep['W_low']) and ep['W_low']>0)
            check('estimated_numerical_envelope:'+name,type(ep['numerical_half_width']) in (int,float) and math.isfinite(ep['numerical_half_width']) and ep['numerical_half_width']>=0)
        for root in (Path(args.study),Path(args.comparison)):
            for path in root.rglob('*.py'):
                if any(x in ('artifacts','__pycache__','.venv','.git') for x in path.relative_to(root).parts): continue
                check('recursive_source_bound:'+str(path),{**source,**bound}.get(key(path))==sha(path))
        check('resource_policy',plan['timeout_seconds']==1800 and plan['total_seconds']==21600 and plan['cleanup_reserve_seconds']==15)
    except Exception as e:
        check('complete_supported_schema',False,f'{type(e).__name__}: {e}')
    return dict(schema='independent_candidate_prelaunch_v1',integrity_pass=bool(checks) and all(c['passed'] for c in checks),qualified=False,checks=checks,scope='Prelaunch evidence only; no fitting, freeze or statistical inference',auditor_sha256=sha(__file__))

def main():
    parser=argparse.ArgumentParser()
    for name in ('plan','protocol','pairs','counts','indices','bank-pin','seed-audit','study','comparison','out'):
        parser.add_argument('--'+name,required=True,type=Path)
    args=parser.parse_args(); result=review(args)
    with args.out.open('x',encoding='utf8') as f: json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps(dict(integrity_pass=result['integrity_pass'],checks=len(result['checks']),failed=sum(not c['passed'] for c in result['checks']))))
    return 0 if result['integrity_pass'] else 2

if __name__=='__main__': raise SystemExit(main())
