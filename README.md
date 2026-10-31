# claude-autotune

An autoresearch-style prompt optimization system for Claude Code. Iteratively improves system prompts using an adversarial Claude-as-judge, inspired by [Andrej Karpathy's autoresearch](https://github.com/karpathy/autoresearch).

## What it does

1. Establishes a baseline system prompt and scores it against 20 real-world test cases
2. Proposes improvements via a prompt engineer agent
3. Scores candidates using an adversarial Claude-as-judge (weighted 5-dimension rubric)
4. Accepts only improvements above a threshold (0.2 points on a 0-10 scale)
5. Versions every accepted prompt via git
6. Requires manual review + Codex spot-check before deployment

## Current target

Optimizing the system prompt for a personal Telegram bot running via `claude --channels plugin:telegram@claude-plugins-official`.

## Structure

```
prompts/          ← versioned system prompts (current.txt symlinks to latest)
tests/            ← 20 test cases across 6 behavioral categories
judge/            ← adversarial judge + proposer prompts
scripts/          ← Python evaluation/proposal scripts + shell orchestration
results/          ← experiment outputs (gitignored)
deploy/           ← launch bot with optimized prompt
```

## Usage

### Setup

```bash
git clone https://github.com/nischal94/claude-autotune
cd claude-autotune
pip3 install anthropic
export ANTHROPIC_API_KEY="sk-ant-..."
ln -sf v001_baseline.txt prompts/current.txt
```

### Run experiment

```bash
ITERATIONS=10 MIN_IMPROVEMENT=0.2 bash scripts/run_experiment.sh
```

### Review and deploy

```bash
cat results/final_report.md
diff prompts/v001_baseline.txt prompts/current.txt
bash deploy/launch_bot.sh
```

### Rollback

```bash
ln -sf v001_baseline.txt prompts/current.txt
bash deploy/launch_bot.sh
```

## Test case categories

| Category | Count | What it tests |
|----------|-------|---------------|
| `calendar_future_filter` | 4 | Only future events shown |
| `ambiguous_nudge` | 4 | "Tell?", "?", "ok", "still there?" |
| `memory_persistence` | 3 | Honest about no cross-session memory |
| `brevity_mobile` | 3 | Concise, mobile-friendly format |
| `tool_transparency` | 2 | Shows work before results |
| `calendar_correction` | 2 | Accepts corrections gracefully |
| `test_validation` | 2 | Verifying changes actually work |

## Judge scoring

| Dimension | Weight |
|-----------|--------|
| Behavioral compliance | 3x |
| Correct behavior for test case | 3x |
| Brevity / mobile suitability | 2x |
| Honesty / no hallucination | 2x |
| Tone | 1x |

Pass threshold: normalized score ≥ 7.0 AND no critical failures.

## Cost estimate

10 iterations × ~41 API calls = ~410 calls total.
Using Haiku for simulation, Sonnet for judge/proposer → under $1 per run.

## License

MIT
