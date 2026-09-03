"""Compile the study's posteriordb models with BridgeStan (no STAN_THREADS, as in posteriordb_bench_v3)
and copy the Stan programs for CmdStan. Usage: python build_models.py [model ...]"""
import json, shutil, sys, time
from pathlib import Path
import bridgestan as bs
from posteriordb import PosteriorDatabase

HERE = Path(__file__).resolve().parent
PDB = PosteriorDatabase(str(HERE / "posteriordb" / "posterior_database"))
MODELS = HERE / "models"
DEFAULT = ["earnings-logearn_interaction", "kidiq-kidscore_momhsiq", "mesquite-logmesquite_logvash", "nes2000-nes",
           "garch-garch11", "arK-arK"]

def short(m): return m.replace("-", "__")

def build(model):
    p = PDB.posterior(model)
    MODELS.mkdir(exist_ok=True)
    stan = MODELS / f"{short(model)}.stan"
    data = MODELS / f"{short(model)}.data.json"
    if not stan.exists(): shutil.copyfile(p.model.code_file_path("stan"), stan)
    if not data.exists(): data.write_text(json.dumps(p.data.values()), encoding="utf-8")
    so = stan.with_name(f"{stan.stem}_model.so")
    if not so.exists():
        t = time.perf_counter(); bs.compile_model(stan, make_args=[]); print(f"compiled {model} {time.perf_counter()-t:.0f}s", flush=True)
    cm = MODELS / "cmdstan"; cm.mkdir(exist_ok=True)
    if not (cm / stan.name).exists(): shutil.copyfile(stan, cm / stan.name)

for m in (sys.argv[1:] or DEFAULT): build(m)
