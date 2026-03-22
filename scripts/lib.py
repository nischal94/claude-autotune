"""Shared utilities for the telegram prompt optimization experiment."""

import json
import os
import subprocess
import sys
from pathlib import Path

import anthropic

EXPERIMENT_DIR = Path(__file__).parent.parent
PROMPTS_DIR = EXPERIMENT_DIR / "prompts"
TESTS_FILE = EXPERIMENT_DIR / "tests" / "inputs.json"
JUDGE_PROMPT_FILE = EXPERIMENT_DIR / "judge" / "judge_prompt.txt"
PROPOSER_PROMPT_FILE = EXPERIMENT_DIR / "judge" / "proposer_prompt.txt"
RESULTS_DIR = EXPERIMENT_DIR / "results"

# Models
SIMULATION_MODEL = "claude-haiku-4-5-20251001"   # cheap, fast for simulation
JUDGE_MODEL = "claude-sonnet-4-6"                 # adversarial judge
PROPOSER_MODEL = "claude-sonnet-4-6"              # prompt engineer


def get_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        # Extract key directly from ~/.zshrc without sourcing the whole file
        zshrc = Path.home() / ".zshrc"
        if zshrc.exists():
            for line in zshrc.read_text().splitlines():
                line = line.strip()
                if "ANTHROPIC_API_KEY" in line and "=" in line:
                    _, _, val = line.partition("=")
                    api_key = val.strip().strip('"').strip("'")
                    break
    if not api_key:
        print("[lib] ERROR: ANTHROPIC_API_KEY not set. Add it to ~/.zshrc.", file=sys.stderr)
        sys.exit(1)
    return anthropic.Anthropic(api_key=api_key)


def call_claude(system: str, user: str, model: str, temperature: float = 0.0, max_tokens: int = 2000) -> str:
    import time
    client = get_client()
    for attempt in range(5):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": user}]
            )
            return response.content[0].text
        except Exception as e:
            if "overloaded" in str(e).lower() and attempt < 4:
                wait = 10 * (attempt + 1)
                print(f"  [retry] API overloaded, waiting {wait}s...", flush=True)
                time.sleep(wait)
            else:
                raise


def read_prompt(path) -> str:
    p = Path(path)
    # Resolve symlink if needed
    if p.is_symlink():
        p = p.resolve()
    return p.read_text().strip()


def load_tests() -> list[dict]:
    return json.loads(TESTS_FILE.read_text())


def read_judge_prompt() -> str:
    return JUDGE_PROMPT_FILE.read_text().strip()


def read_proposer_prompt() -> str:
    return PROPOSER_PROMPT_FILE.read_text().strip()


def save_result(filename: str, data: dict) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / filename
    out.write_text(json.dumps(data, indent=2))
    return out


def parse_json_response(text: str) -> dict:
    """Extract JSON from a response that may have surrounding text."""
    text = text.strip()
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Find JSON block
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
    raise ValueError(f"[lib] Could not parse JSON from response: {text[:200]}")


def git_commit(message: str) -> None:
    subprocess.run(
        ["git", "-C", str(EXPERIMENT_DIR), "add", "prompts/"],
        check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(EXPERIMENT_DIR), "commit", "-m", message],
        check=True, capture_output=True
    )


def build_failure_analysis(scores: list[dict], tests: list[dict]) -> str:
    """Summarize failures grouped by category for the proposer."""
    by_category: dict[str, list] = {}
    test_map = {t["id"]: t for t in tests}

    for score in scores:
        tid = score["test_id"]
        test = test_map.get(tid, {})
        cat = test.get("category", "unknown")
        if score.get("verdict") == "fail":
            by_category.setdefault(cat, []).append({
                "test_id": tid,
                "input": test.get("input", ""),
                "expected": test.get("expected_behavior", ""),
                "critical_failures": score.get("critical_failures", []),
                "normalized_score": score.get("normalized_score", 0),
                "verdict_reason": score.get("verdict_reason", ""),
            })

    if not by_category:
        return "No failures detected. Focus on subtle improvements to already-passing cases."

    lines = []
    for cat, failures in sorted(by_category.items(), key=lambda x: -len(x[1])):
        lines.append(f"\n### Category: {cat} ({len(failures)} failures)")
        for f in failures:
            lines.append(f"- [{f['test_id']}] Input: \"{f['input']}\"")
            lines.append(f"  Score: {f['normalized_score']:.2f} | Reason: {f['verdict_reason']}")
            for cf in f["critical_failures"]:
                lines.append(f"  ✗ {cf}")

    return "\n".join(lines)
