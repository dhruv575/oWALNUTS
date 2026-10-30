from pathlib import Path
study=Path(__file__).resolve().parent
source=(study/'analyze_funnel_error_guard.py').read_text()
needle="(study/'FUNNEL-ERROR-GUARD-ANALYSIS.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\\n')"
assert source.count(needle)==1
source=source.replace(needle,"""def json_safe(value):
    if isinstance(value,dict):return {k:json_safe(v) for k,v in value.items()}
    if isinstance(value,list):return [json_safe(v) for v in value]
    if isinstance(value,float) and not np.isfinite(value):return None
    return value
(study/'FUNNEL-ERROR-GUARD-ANALYSIS.json').write_text(json.dumps(json_safe(report),indent=2,allow_nan=False)+'\\n')""")
(study/'analyze_funnel_error_guard_corrected.py').write_text(source)
