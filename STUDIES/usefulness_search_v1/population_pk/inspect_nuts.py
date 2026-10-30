import inspect,nutpie
print(inspect.signature(nutpie.sample))
s=inspect.getsource(nutpie.sample).splitlines()
for i,l in enumerate(s):
 if any(w in l for w in ['mass_matrix','init_mean','init_inv']):print(i, '\n'.join(s[max(0,i-2):i+4]))
