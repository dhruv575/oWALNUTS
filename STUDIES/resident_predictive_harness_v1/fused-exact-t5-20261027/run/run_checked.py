import subprocess,sys
subprocess.run([sys.argv[1],"-m","unittest","discover","-s",sys.argv[2],"-p","test_harness.py"],check=True)
subprocess.run([sys.argv[1],sys.argv[2]+"/host_smoke.py","--out",sys.argv[3],"--numerical-backend","exact_t5","--baseline",sys.argv[4]],check=True)
