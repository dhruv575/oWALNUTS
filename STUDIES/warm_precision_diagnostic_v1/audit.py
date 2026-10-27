"""Read-only completeness and paired pre-shock replay checks after recovery."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = json.loads((HERE/"protocol.json").read_text())
ART = HERE/"artifacts"
rows = []
for cell in P["cells"]:
    root = ART/"cells"/cell["id"]
    path = root/"ticks.jsonl"
    recs = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    ticks = [r["tick"] for r in recs]
    errors = []
    if len(ticks) != len(set(ticks)):
        errors.append("duplicate tick")
    missing = sorted(set(range(P["ticks"]+1))-set(ticks))
    unexpected = sorted(set(ticks)-set(range(P["ticks"]+1)))
    non_ok = [r["tick"] for r in recs if r.get("status") != "ok"]
    for r in recs:
        t = r["tick"]
        if r.get("status") != "ok" or t % P["save_every"]:
            continue
        raw = root/f"tick-{t:04}.f32"
        expected = r["chains"]*r["draws"]*3*4
        if not raw.exists() or raw.stat().st_size != expected:
            errors.append(f"bad draw file {raw.name}")
        if t and r["draws"] != cell["K"]:
            errors.append(f"unexpected retained count at tick {t}")
    rows.append(dict(cell=cell["id"], records=len(recs), missing_ticks=missing,
                     unexpected_ticks=unexpected, non_ok_ticks=non_ok, errors=errors))
pairs = []
for k in (200, 400, 800):
    for tick in range(0, 1001, 25):
        paths = [ART/"cells"/f"warm-K{k}-{stream}-s{P['sampler_seed']}"/f"tick-{tick:04}.f32" for stream in ("shift", "control")]
        hashes = [hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None for p in paths]
        pairs.append(dict(K=k, tick=tick, hashes=hashes, identical=hashes[0] is not None and hashes[0] == hashes[1]))
result = dict(kind="post-run integrity and deterministic pairing audit, not a qualification gate", cells=rows,
              all_cells_complete=all(not r["missing_ticks"] and not r["unexpected_ticks"] and not r["non_ok_ticks"] and not r["errors"] for r in rows),
              paired_pre_shock_files=pairs, paired_identical=sum(p["identical"] for p in pairs), paired_planned=len(pairs))
out = ART/"recovery-audit.json"
if out.exists():
    raise SystemExit("Preserving existing audit output")
out.write_text(json.dumps(result, indent=2)+"\n", newline="\n")
print(json.dumps({k: result[k] for k in ("all_cells_complete", "paired_identical", "paired_planned")}))
