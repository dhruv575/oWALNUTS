"""Aggregate the three sub-study summaries into artifacts/summary.json and
RESULTS.md, then write CHECKSUMS.sha256 over protocols, sources, and artifacts.

Usage: python summarize.py
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
ART.mkdir(exist_ok=True)


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    tr = load(HERE / "truncated/artifacts/summary.json")
    fu = load(HERE / "funnel/artifacts/summary.json")
    sw = load(HERE / "stock_watson/artifacts/summary.json")
    out = {"schema": "owalnuts-invalid-evaluation-parity-summary/v1", "truncated": tr, "funnel": fu, "stock_watson": sw}
    (ART / "summary.json").write_text(json.dumps(out, indent=1), encoding="utf-8")

    lines = ["# Results — invalid-evaluation parity v1 (kernel v10)", ""]
    m = tr["moments"]
    r = tr["retained"]
    lines += ["## Truncated Gaussian (recoverable-error wall at x0 = 0)", "",
              "| functional | R-hat | bulk ESS | tail ESS | mean (exact) | z | variance (exact) | z |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for k, v in m.items():
        lines.append(f"| {k} | {v['rhat']:.4f} | {v['bulk_ess']:.0f} | {v['tail_ess']:.0f} | {v['mean']:.4f} ({v['exact_mean']:.4f}) | {v['mean_z']:+.2f} | {v['variance']:.4f} ({v['exact_variance']:.4f}) | {v['variance_z']:+.2f} |")
    lines += ["", f"Retained: {r['recoverable_target_failures']} recoverable failures = {r['zero_density_evaluations']} zero-density evaluations; "
              f"{r['invalid_evaluation_stops']} invalid-evaluation stops; {r['divergences']} divergences; "
              f"{r['refinement_exhaustion_stops']} exhaustion stops of {tr['chains'] * tr['retained_per_chain']} transitions; "
              f"stops {r['stops']}; gates {'PASS' if tr['passed'] else 'FAIL'} ({tr['gates']}).", ""]
    lines += ["## Funnel gate at paper tuning (v10)", "", "```", json.dumps({k: fu[k] for k in fu if k != 'arms'} if isinstance(fu, dict) and 'arms' in fu else fu, indent=1)[:4000], "```", ""]
    lines += ["## Stock–Watson arms F and A without -inf emulation", "", "```", json.dumps(sw, indent=1)[:6000], "```", ""]
    (HERE / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")

    files = []
    for sub in ("truncated", "funnel", "stock_watson"):
        d = HERE / sub
        files += [d / "protocol.json", d / "analyze.py", d / "src" / "main.rs", d / "Cargo.toml"]
        files += sorted((d / "artifacts").glob("*.json"))
    files += [HERE / "PREREGISTRATION.md", HERE / "summarize.py", ART / "summary.json",
              HERE.parents[1] / "src" / "kernel.rs", HERE.parents[1] / "src" / "walnutpie.rs"]
    with (HERE / "CHECKSUMS.sha256").open("w", encoding="utf-8", newline="\n") as fh:
        for f in files:
            if f.is_file():
                fh.write(f"{sha(f)} *{f.relative_to(HERE.parents[1]).as_posix()}\n")
    print("summary and checksums written")


if __name__ == "__main__":
    main()
