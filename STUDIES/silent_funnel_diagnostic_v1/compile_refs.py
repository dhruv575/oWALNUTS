import cmdstanpy, sys, time
from pathlib import Path
cmdstanpy.set_cmdstan_path(r"C:\dev\polyscope\STUDIES\matched_competitor_eight_schools_v38\cmdstan\cmdstan-2.39.0")
for name in sys.argv[1:]:
    t = time.time()
    cmdstanpy.CmdStanModel(stan_file=str(Path(__file__).parent / "reference_models" / f"{name}.stan"))
    print(name, "compiled", round(time.time() - t, 1), "s", flush=True)
