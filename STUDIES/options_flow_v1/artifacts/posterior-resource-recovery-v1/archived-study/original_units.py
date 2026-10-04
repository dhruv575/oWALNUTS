"""Affine inversion for prediction summaries; parameter transformations differ."""
import copy
import math


def forecast_in_original_units(forecast,fixture):
    scaling=fixture.get('scaling')
    if scaling is None:return None
    mean,sd=float(scaling['y_mean']),float(scaling['y_sd'])
    if not math.isfinite(mean) or not math.isfinite(sd) or sd<=0:
        raise ValueError('Invalid recorded outcome scaling')
    result=copy.deepcopy(forecast)
    for row in result.get('rows',[]):
        for key in ('lower','upper','observed'):
            if key in row:row[key]=mean+sd*row[key]
        for key in ('width','interval_score'):
            if key in row:row[key]*=sd
        if 'endpoint_mcse' in row:row['endpoint_mcse']=[sd*v for v in row['endpoint_mcse']]
    if 'mean_interval_score' in result:result['mean_interval_score']*=sd
    result['units']=fixture.get('provenance',{}).get('y_units','declared input units')
    result['transformation']='y_original = training_y_mean + training_y_sd*y_standardized'
    return result
