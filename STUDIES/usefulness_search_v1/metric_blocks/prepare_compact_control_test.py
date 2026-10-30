from pathlib import Path
study=Path(__file__).resolve().parent
s=(study/'test_compact_recycling.py').read_text().replace('compact_recycling_test01','compact_original_test01').replace('compact_recycling_build01','compact_original_build01').replace('compact_recycling_runner/src/main.rs','compact_original_runner/src/main.rs').replace("for arm in ['original','observed']:","for arm in ['original']:")
a=s.index('        if batch==0:');b=s.index('    print(target+',a);s=s[:a]+s[b:]
s=s.replace('full_mode_exact_cases=3','full_mode_exact_cases=0').replace('all compact and full-mode checks passed','all original-kernel compact checks passed')
(study/'test_compact_original.py').write_text(s)
