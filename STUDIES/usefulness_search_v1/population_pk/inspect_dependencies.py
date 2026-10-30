import importlib.metadata as m
for p in ['numpy','scipy','arviz','cachetools','cloudpickle','pandas','rich','typing-extensions','filelock','etuples','logical-unification','miniKanren','cons','setuptools']:
 try:print(p,m.version(p))
 except m.PackageNotFoundError:print(p,'MISSING')
