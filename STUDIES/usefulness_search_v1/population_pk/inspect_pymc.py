import inspect,pymc as pm
print(pm.__version__)
print(inspect.signature(pm.NUTS))
print(inspect.signature(pm.step_methods.hmc.base_hmc.BaseHMC))
print(inspect.getsource(pm.step_methods.hmc.base_hmc.BaseHMC.__init__))
