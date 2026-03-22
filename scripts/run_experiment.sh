#!/usr/bin/env bash
# Telegram Prompt Optimization Experiment Runner
#
# Usage:
#   ITERATIONS=10 MIN_IMPROVEMENT=0.2 bash scripts/run_experiment.sh
#   ITERATIONS=3 bash scripts/run_experiment.sh   # quick test run

set -euo pipefail

EXPERIMENT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPTS="$EXPERIMENT_DIR/scripts"
PROMPTS="$EXPERIMENT_DIR/prompts"
RESULTS="$EXPERIMENT_DIR/results"

ITERATIONS="${ITERATIONS:-10}"
MIN_IMPROVEMENT="${MIN_IMPROVEMENT:-0.2}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG="$RESULTS/experiment_${TIMESTAMP}.log"

mkdir -p "$RESULTS"

log() {
    local msg="[$(date '+%H:%M:%S')] $*"
    echo "$msg"
    echo "$msg" >> "$LOG"
}

score_of() {
    python3 -c "import json,sys; d=json.load(open('$1')); print(d['avg_score'])"
}

cd "$EXPERIMENT_DIR"

# ── Extract ANTHROPIC_API_KEY from zshrc if not set ─────────────────────────
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    ANTHROPIC_API_KEY=$(grep 'ANTHROPIC_API_KEY=' ~/.zshrc | head -1 | sed 's/.*ANTHROPIC_API_KEY=//' | tr -d '"' | tr -d "'")
    export ANTHROPIC_API_KEY
fi

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    echo "[ERROR] ANTHROPIC_API_KEY not set. Add it to ~/.zshrc." >&2
    exit 1
fi

# Unset SOCKS proxy vars — httpx requires 'socksio' for socks5://, which isn't
# installed. api.anthropic.com is in the sandbox allowlist so no proxy needed.
unset ALL_PROXY all_proxy FTP_PROXY ftp_proxy GRPC_PROXY grpc_proxy

log "===== Telegram Prompt Optimization Experiment ====="
log "Iterations: $ITERATIONS | Min improvement: $MIN_IMPROVEMENT"
log "Log: $LOG"

# ── Step 1: Establish baseline ───────────────────────────────────────────────
BASELINE_FILE="$RESULTS/baseline.json"

if [ -f "$BASELINE_FILE" ]; then
    log "Baseline already exists, skipping..."
else
    log "Evaluating baseline prompt..."
    python3 "$SCRIPTS/evaluate.py" \
        --prompt-file "$PROMPTS/current.txt" \
        --output "$BASELINE_FILE"
fi

BASELINE_SCORE=$(score_of "$BASELINE_FILE")
BEST_SCORE="$BASELINE_SCORE"
BEST_PROMPT="$PROMPTS/current.txt"
BEST_RESULT_FILE="$BASELINE_FILE"

log "Baseline score: $BASELINE_SCORE"

# ── Step 2: Iteration loop ───────────────────────────────────────────────────
for i in $(seq 1 "$ITERATIONS"); do
    log ""
    log "=== Iteration $i / $ITERATIONS ==="

    CANDIDATE_FILE="$RESULTS/candidate_iter_$(printf '%03d' $i).txt"
    RESULT_FILE="$RESULTS/iter_$(printf '%03d' $i).json"

    # Propose next candidate
    log "Proposing candidate prompt..."
    python3 "$SCRIPTS/propose.py" \
        --prompt-file "$BEST_PROMPT" \
        --baseline-score "$BASELINE_SCORE" \
        --current-score "$BEST_SCORE" \
        --failure-file "$BEST_RESULT_FILE" \
        --iteration "$i" \
        --output "$CANDIDATE_FILE"

    # Evaluate candidate
    log "Evaluating candidate..."
    python3 "$SCRIPTS/evaluate.py" \
        --prompt-file "$CANDIDATE_FILE" \
        --output "$RESULT_FILE"

    CANDIDATE_SCORE=$(score_of "$RESULT_FILE")
    log "Candidate score: $CANDIDATE_SCORE | Best so far: $BEST_SCORE"

    # Accept if improved by MIN_IMPROVEMENT
    IMPROVED=$(python3 -c "print('yes' if float('$CANDIDATE_SCORE') >= float('$BEST_SCORE') + float('$MIN_IMPROVEMENT') else 'no')")

    if [ "$IMPROVED" = "yes" ]; then
        # Version the accepted prompt
        VERSION_NUM=$(ls "$PROMPTS"/v*.txt 2>/dev/null | wc -l | tr -d ' ')
        VERSION_NUM=$((VERSION_NUM + 1))
        VERSION=$(printf 'v%03d' "$VERSION_NUM")
        NEW_PROMPT_FILE="$PROMPTS/${VERSION}_iter${i}.txt"

        cp "$CANDIDATE_FILE" "$NEW_PROMPT_FILE"
        ln -sf "$(basename "$NEW_PROMPT_FILE")" "$PROMPTS/current.txt"

        BEST_SCORE="$CANDIDATE_SCORE"
        BEST_PROMPT="$NEW_PROMPT_FILE"
        BEST_RESULT_FILE="$RESULT_FILE"

        # Mark as accepted in result
        python3 -c "
import json
f = '$RESULT_FILE'
d = json.load(open(f))
d['accepted'] = True
d['prompt_version'] = '$VERSION'
open(f, 'w').write(json.dumps(d, indent=2))
"
        git -C "$EXPERIMENT_DIR" add prompts/ 2>/dev/null || true
        git -C "$EXPERIMENT_DIR" commit -m "feat(prompt): iter $i accepted — score $CANDIDATE_SCORE (was $BEST_SCORE)" 2>/dev/null || true

        log "ACCEPTED → $NEW_PROMPT_FILE (score: $CANDIDATE_SCORE)"
    else
        # Mark as rejected in result
        python3 -c "
import json
f = '$RESULT_FILE'
d = json.load(open(f))
d['accepted'] = False
open(f, 'w').write(json.dumps(d, indent=2))
"
        log "REJECTED — score $CANDIDATE_SCORE did not beat $BEST_SCORE + $MIN_IMPROVEMENT"
    fi
done

# ── Step 3: Final report ─────────────────────────────────────────────────────
log ""
log "===== Experiment Complete ====="
log "Baseline:  $BASELINE_SCORE"
log "Best:      $BEST_SCORE"
log "Best file: $BEST_PROMPT"
log ""

python3 "$SCRIPTS/report.py" \
    --results-dir "$RESULTS" \
    --output "$RESULTS/final_report.md"

log ""
log "Next steps:"
log "  1. Review: cat $RESULTS/final_report.md"
log "  2. Diff:   diff $PROMPTS/v001_baseline.txt $PROMPTS/current.txt"
log "  3. Paste prompts/current.txt into Codex for second-opinion"
log "  4. Deploy: bash $EXPERIMENT_DIR/deploy/launch_bot.sh"
log "  5. Rollback if needed: ln -sf v001_baseline.txt $PROMPTS/current.txt"
