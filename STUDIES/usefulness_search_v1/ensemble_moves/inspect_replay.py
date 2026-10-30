import inspect,json
import bridgestan
print(inspect.signature(bridgestan.StanModel))
print(inspect.signature(bridgestan.StanModel.log_density_gradient))
x=json.load(open('/dev/shm/bounded-init-20261030/run01/012/RESULT.json'))
print(list(x['chains_data'][0]))
print('samples',len(x['chains_data'][0]['samples']),len(x['chains_data'][0]['samples'][0]))
