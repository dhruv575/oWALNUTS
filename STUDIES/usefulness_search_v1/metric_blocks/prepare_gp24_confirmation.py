from pathlib import Path
p=Path(__file__).resolve().parent
s=(p/'bounded_gp_validation_worker.py').read_text()
old="refpath=LOCAL/'localscaled01/REFERENCES.json';ref=json.loads(refpath.read_text())[name];assert ref['passed']"
new="refpath=STUDY.parent/'gp_count/REFERENCE.json';reference=json.loads(refpath.read_text());assert reference['qualified'];ref=dict(reference['stats'],names=reference['names']);assert len(ref['names'])==24"
assert old in s;s=s.replace(old,new).replace("for n in ref['names']]","for n in ref['names'][:13]]")
old=".reshape(4,8000,-1);np.savez_compressed(root/'FUNCTIONALS.npz',values=values)"
new=".reshape(4,8000,-1);assert values.shape==(4,8000,13);values=np.concatenate([values,np.exp(values[:,:,2:])],axis=2);assert np.isfinite(values).all();np.savez_compressed(root/'FUNCTIONALS.npz',values=values)"
assert old in s;s=s.replace(old,new).replace('max(z)<=4.5','max(z)<=4').replace('BOUNDED-GP-VALIDATION-PROTOCOL.md','GP-24-CONFIRMATION-PROTOCOL.md')
compile(s,'gp24_confirmation_worker.py','exec');(p/'gp24_confirmation_worker.py').write_text(s)
s=(p/'run_bounded_gp_validation.py').read_text().replace('bounded_gp_validation','gp24_confirmation').replace('BOUNDED-GP-VALIDATION-PROTOCOL.md','GP-24-CONFIRMATION-PROTOCOL.md').replace('948700001','949000001').replace('948800001','949100001')
s=s.replace("('raw','low_rank',.99)","('raw','diag',.999)").replace("('bounded','low_rank',.99)","('bounded','diag',.999)")
start=s.index('for transform,mode,accept in configs[4:]:');end=s.index('hashes=',start)
s=s[:start]+"""repair=json.loads((l/'bounded_gp_native_repair01/SUMMARY.json').read_text());assert repair['completed']
for transform,mode,accept in [configs[1],configs[5]]:
    selected=next(x['selection'] for x in repair['selected'] if x['transform']==transform);assert selected['mode']==mode and selected['target_accept']==accept
selected=next(x['selection'] for x in cal['selected'] if x['engine']=='walnuts');assert selected['mode']==configs[4][1] and selected['target_accept']==configs[4][2]
"""+s[end:]
compile(s,'run_gp24_confirmation.py','exec');(p/'run_gp24_confirmation.py').write_text(s)
print('Prepared48 fresh24-function confirmation fits')
