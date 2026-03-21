"""
Propose a new candidate system prompt based on failure analysis.

Usage:
  python3 propose.py --prompt-file prompts/current.txt \
    --baseline-score 6.5 --current-score 6.8 \
    --failure-file results/iter_001.json \
    --iteration 1 \
    --output results/candidate_iter_001.txt
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib import PROPOSER_MODEL, call_claude, read_prompt, read_proposer_prompt


def propose_next(
    current_prompt: str,
    iteration: int,
    baseline_score: float,
    current_score: float,
    failure_analysis: str,
) -> str:
    template = read_proposer_prompt()
    filled = template.format(
        CURRENT_PROMPT=current_prompt,
        ITERATION=iteration,
        BASELINE_SCORE=f"{baseline_score:.2f}",
        CURRENT_SCORE=f"{current_score:.2f}",
        FAILURE_ANALYSIS=failure_analysis,
    )
    return call_claude(
        system="You are a prompt engineer. Output only the revised system prompt text, nothing else.",
        user=filled,
        model=PROPOSER_MODEL,
        temperature=0.7,
        max_tokens=1000
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--baseline-score", type=float, required=True)
    parser.add_argument("--current-score", type=float, required=True)
    parser.add_argument("--failure-file", required=True)
    parser.add_argument("--iteration", type=int, required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    current_prompt = read_prompt(args.prompt_file)
    failure_data = json.loads(Path(args.failure_file).read_text())
    failure_analysis = failure_data.get("failure_analysis", "No failure analysis available.")

    print(f"[propose] Generating candidate prompt for iteration {args.iteration}...")
    new_prompt = propose_next(
        current_prompt=current_prompt,
        iteration=args.iteration,
        baseline_score=args.baseline_score,
        current_score=args.current_score,
        failure_analysis=failure_analysis,
    )

    Path(args.output).write_text(new_prompt)
    print(f"[propose] Candidate written to: {args.output}")
    print(f"[propose] Prompt length: {len(new_prompt)} chars ({len(new_prompt.split())} words)")


if __name__ == "__main__":
    main()
