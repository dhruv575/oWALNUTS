"""Pure-integer public/declared-guard seed reservation; never constructs an RNG."""
MASK=(1<<64)-1
INIT=0x5eed141700000000
RESTART=0x7472617070656400

def splitmix(value):
    value=(value+0x9e3779b97f4a7c15)&MASK
    value=((value^(value>>30))*0xbf58476d1ce4e5b9)&MASK
    value=((value^(value>>27))*0x94d049bb133111eb)&MASK
    return value^(value>>31)

def native_roles(initial,warm,updates):
    initial_raw=[(initial+c)&MASK for c in range(4)];effective=[splitmix(x) for x in initial_raw]
    restart_start=[(splitmix(initial^RESTART)+c)&MASK for c in range(4)]
    warm_raw=[(warm+4*j+c)&MASK for j in range(updates) for c in range(4)]
    return dict(initial_chain_inputs=initial_raw,initial_effective=effective,initial_tagged=[splitmix(initial^INIT)],restart_start_base=restart_start,restart_start_effective=[splitmix(x^INIT) for x in restart_start],restart_chain=[splitmix(x^RESTART) for x in effective],warm_call_inputs=warm_raw,warm_effective=[splitmix(x) for x in warm_raw])

def flatten(roles):return {x for values in roles.values() for x in values}

def combined(e61):
    # Reproduce the already audited E61 derivations before reserving new values.
    for stream in range(32):
        expected=native_roles(2026102702000000+1000*stream,2026102703000000+1000*stream,32)
        for role in ('initial_effective','initial_tagged','restart_start_base','restart_start_effective','restart_chain','warm_call_inputs','warm_effective'):
            if expected[role]!=e61['roles'][role+':'+str(stream)]:raise ValueError('E61 derivation mismatch '+role)
    sets={'e61':flatten(e61['roles'])};roles={}
    for rep in range(2):
        for role,values in native_roles(2026102707000000+100000*rep,2026102708000000+100000*rep,2000).items():roles[f'{role}:rep{rep}']=values
    roles['data']=[2026102706000000];roles['reference_sample_and_model']=[312710000+1000*j+c for j in range(18) for c in range(2)]
    replicate_sets=[flatten({k:v for k,v in roles.items() if k.endswith(':rep'+str(i))}) for i in range(2)]
    if replicate_sets[0]&replicate_sets[1]:raise ValueError('Within-long sampler-replicate seed collision')
    shared_context=set(roles['data']+roles['reference_sample_and_model'])
    if (replicate_sets[0]|replicate_sets[1])&shared_context:raise ValueError('Long data/reference/native seed collision')
    sets['long']=flatten(roles)
    real=native_roles(2026102711000000,2026102712000000,1488);real['bootstrap']=[2026102713000000];real['reference_sample_and_model']=[402711000+1000*j+c for j in range(8) for c in range(2)];sets['real']=flatten(real)
    development=native_roles(993711000,993712000,32);development['reference']=[993713000,993713001];development['independent_preflight']=[99371041,99371042];sets['development']=flatten(development)
    collisions={}
    names=list(sets)
    for i,left in enumerate(names):
        for right in names[i+1:]:
            values=sorted(sets[left]&sets[right])
            if values:collisions[left+'__'+right]=values
    return dict(roles=roles,real_roles=real,sets=sets,collisions=collisions)
