"""
Generate a human-readable markdown report after an experiment run.

Usage:
  python3 report.py --results-dir results/ --output results/final_report.md
"""

import argparse
import json
from pathlib import Path


def load_iteration_results(results_dir: Path) -> list[dict]:
    files = sorted(results_dir.glob("iter_*.json"))
    results = []
    for f in files:
        data = json.loads(f.read_text())
        data["_file"] = f.name
        results.append(data)
    return results


def load_baseline(results_dir: Path) -> dict | None:
    f = results_dir / "baseline.json"
    if f.exists():
        return json.loads(f.read_text())
    return None


def generate_report(results_dir: Path, output_path: Path) -> None:
    baseline = load_baseline(results_dir)
    iterations = load_iteration_results(results_dir)

    lines = ["# Telegram Prompt Optimization — Experiment Report\n"]

    # Baseline
    if baseline:
        lines.append("## Baseline")
        lines.append(f"- Score: **{baseline['avg_score']:.2f}/10**")
        lines.append(f"- Pass: {baseline['pass_count']} | Fail: {baseline['fail_count']} | Total: {baseline['total']}")
        lines.append("")

    # Iteration summary table
    if iterations:
        lines.append("## Iteration Summary")
        lines.append("")
        lines.append("| Iter | Score | vs Baseline | Pass | Fail | Accepted |")
        lines.append("|------|-------|-------------|------|------|----------|")
        baseline_score = baseline["avg_score"] if baseline else 0
        for i, r in enumerate(iterations, 1):
            score = r.get("avg_score", 0)
            delta = score - baseline_score
            delta_str = f"+{delta:.2f}" if delta >= 0 else f"{delta:.2f}"
            accepted = r.get("accepted", "?")
            lines.append(
                f"| {i} | {score:.2f} | {delta_str} | {r.get('pass_count',0)} | {r.get('fail_count',0)} | {'✓' if accepted else '✗'} |"
            )
        lines.append("")

    # Best result
    if iterations:
        best = max(iterations, key=lambda x: x.get("avg_score", 0))
        lines.append(f"## Best Result")
        lines.append(f"- Score: **{best['avg_score']:.2f}/10** (file: {best['_file']})")
        lines.append(f"- Improvement over baseline: **{best['avg_score'] - baseline_score:+.2f}**")
        lines.append("")

    # Failure analysis from best run
    if iterations and best.get("failure_analysis"):
        lines.append("## Remaining Failures (Best Run)")
        lines.append("```")
        lines.append(best["failure_analysis"])
        lines.append("```")
        lines.append("")

    # Next steps
    lines.append("## Next Steps")
    lines.append("1. Review `prompts/current.txt` diff vs `prompts/v001_baseline.txt`")
    lines.append("2. Paste `prompts/current.txt` into Codex for second-opinion review")
    lines.append("3. If approved: `bash deploy/launch_bot.sh`")
    lines.append("4. If rolling back: `ln -sf v001_baseline.txt prompts/current.txt`")
    lines.append("")
    lines.append("To expand test set: add cases to `tests/inputs.json` and re-run baseline.")

    report = "\n".join(lines)
    output_path.write_text(report)
    print(f"[report] Report written to: {output_path}")
    print(report)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    generate_report(Path(args.results_dir), Path(args.output))


if __name__ == "__main__":
    main()
