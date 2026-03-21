"""
Evaluate a candidate system prompt against the test suite.

Usage:
  python3 evaluate.py --prompt-file prompts/current.txt --output results/baseline.json
  python3 evaluate.py --prompt-file prompts/current.txt --subset 3 --output /dev/stdout
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib import (
    SIMULATION_MODEL, JUDGE_MODEL,
    build_failure_analysis, call_claude, load_tests,
    parse_json_response, read_judge_prompt, read_prompt, save_result
)


def simulate_response(system_prompt: str, test: dict) -> str:
    """Ask Claude to simulate how the bot would respond given this system prompt."""
    user_msg = f"""A Telegram bot is running with the following system prompt:

<system_prompt>
{system_prompt}
</system_prompt>

Simulate the bot's EXACT response to this Telegram message from the user:

User message: "{test['input']}"
Context: {test['context']}

Write ONLY the bot's response text, exactly as it would appear in Telegram.
Do not add any commentary, explanation, or formatting outside the response itself.
"""
    return call_claude(
        system="You simulate Telegram bot responses. Output only the bot's reply text, nothing else.",
        user=user_msg,
        model=SIMULATION_MODEL,
        temperature=0.0,
        max_tokens=500
    )


def score_response(system_prompt: str, test: dict, simulated_response: str) -> dict:
    """Use the adversarial judge to score a simulated response."""
    judge_prompt = read_judge_prompt()
    user_msg = f"""<system_prompt>
{system_prompt}
</system_prompt>

<test_input>
  <test_id>{test['id']}</test_id>
  <user_message>{test['input']}</user_message>
  <context>{test['context']}</context>
  <expected_behavior>{test['expected_behavior']}</expected_behavior>
</test_input>

<simulated_response>
{simulated_response}
</simulated_response>"""

    raw = call_claude(
        system=judge_prompt,
        user=user_msg,
        model=JUDGE_MODEL,
        temperature=0.0,
        max_tokens=800
    )
    result = parse_json_response(raw)
    result["simulated_response"] = simulated_response
    return result


def evaluate_prompt(prompt_text: str, tests: list[dict], verbose: bool = False) -> dict:
    """Evaluate a prompt against all tests. Returns aggregate results."""
    scores = []
    for i, test in enumerate(tests):
        if verbose:
            print(f"  [{i+1}/{len(tests)}] {test['id']} ({test['category']})...", end=" ", flush=True)

        simulated = simulate_response(prompt_text, test)
        score = score_response(prompt_text, test, simulated)
        scores.append(score)

        if verbose:
            verdict = score.get("verdict", "?")
            ns = score.get("normalized_score", 0)
            print(f"{verdict.upper()} ({ns:.2f})")

    avg_score = sum(s.get("normalized_score", 0) for s in scores) / len(scores)
    fail_count = sum(1 for s in scores if s.get("verdict") == "fail")
    pass_count = len(scores) - fail_count
    failure_analysis = build_failure_analysis(scores, tests)

    return {
        "avg_score": round(avg_score, 4),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "total": len(scores),
        "failure_analysis": failure_analysis,
        "scores": scores,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--subset", type=int, default=None, help="Only run N tests (for dry runs)")
    parser.add_argument("--verbose", action="store_true", default=True)
    args = parser.parse_args()

    prompt_text = read_prompt(args.prompt_file)
    tests = load_tests()

    if args.subset:
        tests = tests[:args.subset]
        print(f"[evaluate] Dry run: using {args.subset} of {len(load_tests())} tests")

    print(f"[evaluate] Evaluating prompt from: {args.prompt_file}")
    print(f"[evaluate] Running {len(tests)} test cases...")

    result = evaluate_prompt(prompt_text, tests, verbose=args.verbose)

    print(f"\n[evaluate] Score: {result['avg_score']:.2f}/10 | Pass: {result['pass_count']} | Fail: {result['fail_count']}")

    output = json.dumps(result, indent=2)
    if args.output == "/dev/stdout":
        print(output)
    else:
        Path(args.output).write_text(output)
        print(f"[evaluate] Results saved to: {args.output}")

    return result["avg_score"]


if __name__ == "__main__":
    main()
