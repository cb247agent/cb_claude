#!/bin/bash
# _common.sh — shared setup for every phase script. Sourced (not executed)
# by each scripts/phases/phase*.sh and by the master scripts/weekly-report.sh.
#
# WHY THIS FILE EXISTS
# Pre-Wave-D, weekly-report.sh was 985 lines. Splitting it phase-by-phase
# means each phase has to re-declare the env-loading, model routing, log
# helpers, run_agent wrapper, output paths, etc. — duplication waiting to
# rot. Hoisting them here means each phase becomes a single-responsibility
# 80-200 line script that's easy to read + edit.
#
# WHAT THIS PROVIDES (exported / global)
#   $BASE_DIR        — absolute path to the project root
#   $PYTHON          — venv interpreter
#   $CLAUDE          — Claude Code CLI
#   $MODEL_{HAIKU,SONNET,OPUS}  — model routing
#   $LOG             — path to the main log file (state/weekly-report.log)
#   $DATE            — today's date in YYYY-MM-DD
#   $OUTPUTS, $STATE — convenience paths
#   FAILED_AGENTS    — array, agents add their names on failure (preserved
#                       across phases because every phase sources this file)
#   log()            — timestamped tee to $LOG
#   fail()           — log an ERROR prefix
#   run_agent()      — invoke Claude Code with the project's standard wrapper

# Guard against double-sourcing — idempotent.
[[ -n "${_CB247_COMMON_SOURCED:-}" ]] && return 0
export _CB247_COMMON_SOURCED=1

# BASE_DIR resolves from this file's location (so phase scripts work no
# matter where they're called from).
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Load environment (.env) if present. Safe parser skips bad lines.
if [ -f "$BASE_DIR/.env" ]; then
    while IFS='=' read -r key val; do
        [[ -z "$key" || "$key" =~ ^[[:space:]]*# || ! "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] && continue
        export "$key"="$val"
    done < "$BASE_DIR/.env"
fi

PYTHON="$BASE_DIR/.venv/bin/python3.13"
CLAUDE="/Users/tiachasingbetter/.local/bin/claude"

# Model routing — Max subscription. Env vars override the defaults.
MODEL_HAIKU="${ANTHROPIC_DEFAULT_HAIKU_MODEL:-claude-haiku-4-5}"
MODEL_SONNET="${ANTHROPIC_DEFAULT_SONNET_MODEL:-claude-sonnet-4-5}"
MODEL_OPUS="${ANTHROPIC_DEFAULT_OPUS_MODEL:-claude-opus-4-5}"

LOG="$BASE_DIR/state/weekly-report.log"
DATE=$(date '+%Y-%m-%d')
OUTPUTS="$BASE_DIR/outputs"
STATE="$BASE_DIR/state"

# Ensure output dirs exist (idempotent).
mkdir -p \
    "$OUTPUTS/research" \
    "$OUTPUTS/seo" \
    "$OUTPUTS/content" \
    "$OUTPUTS/blueprints" \
    "$OUTPUTS/creatives" \
    "$OUTPUTS/qa" \
    "$OUTPUTS/security" \
    "$BASE_DIR/logs/agents"

# FAILED_AGENTS preserved across phase scripts. Each phase script can
# append to it — they all share the same parent shell because weekly-
# report.sh sources phases (not subshells them).
FAILED_AGENTS=("${FAILED_AGENTS[@]:-}")
# Clean any empty initial slot
[[ "${FAILED_AGENTS[0]:-}" == "" ]] && FAILED_AGENTS=()

log()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG"; }
fail() { log "ERROR: $1"; }

run_agent() {
    local name="$1"
    local prompt="$2"
    local out="$3"
    local tools="${4:-Read(context/**),Read(outputs/**)}"
    local model="${5:-$MODEL_SONNET}"
    local agent_log="$BASE_DIR/logs/agents/$(date +%Y-%m-%d)-${name}.log"

    log "  → [$model] Running $name..."
    if "$CLAUDE" \
        --allowedTools "$tools" \
        --model "$model" \
        --print \
        --output-format text \
        "$prompt" > "$out" 2>"$agent_log"; then
        log "  ✅ $name complete → $(basename "$out")"
        return 0
    else
        FAILED_AGENTS+=("$name")
        log "  ❌ $name FAILED — log: logs/agents/$(basename "$agent_log")"
        return 0   # always return 0 — failures tracked in FAILED_AGENTS[]
    fi
}
