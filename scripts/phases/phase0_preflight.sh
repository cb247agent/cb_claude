#!/bin/bash
# phase0_preflight.sh — Wave A dev-cycle + Wave B security agent.
#
# Runs BEFORE Phase 1 data pulls so we catch:
#   - Schema drift between schema.py and Supabase CHECK constraints
#   - Stale workflow vocab in emitter descriptions
#   - Strategist chain regressions
#   - Vulnerable dependencies
#   - Leaked credentials in commits / working tree
#   - Supabase RLS regressions
#
# Warn-only by default. Promote to blocking by adding --strict in
# scripts/dev-cycle.sh or in the run_agent invocation here.
#
# Sourced + run from scripts/weekly-report.sh.

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

log ""
log "─── PHASE 0a: DEV CYCLE PRE-FLIGHT ───"
bash "$BASE_DIR/scripts/dev-cycle.sh" --pre-flight >> "$LOG" 2>&1 \
    || log "  ⚠️  dev-cycle pre-flight had blocking errors — check $LOG"
log "Phase 0a complete."

log ""
log "─── PHASE 0b: SECURITY AGENT ───"
mkdir -p "$OUTPUTS/security"
run_agent "security-agent" \
"You are the CB247 Security Agent. Today is $DATE.

Walk the last 7 days of commits + the working tree for leaked credentials,
verify .gitignore strength, probe Supabase RLS coverage on the 4 critical
tables, and audit .claude/settings.json.

Read these files:
- .gitignore
- .claudeignore
- db/policies.sql
- db/schema.sql

Critical safety rule: NEVER print actual secret values. When you find a
leaked secret, redact the middle (first 4 chars + '...' + last 4 chars)
and name the platform the key belongs to.

Use grep against the working tree + git log --since=\"7 days ago\" for
known credential patterns (sk-ant-, sk-or-v1-, apify_api_, sb_secret_,
AKIA, GOCSPX-, BEGIN PRIVATE KEY).

Probe Supabase RLS via curl: anon DELETE on each table should fail with
401/403. anon SELECT + UPSERT should succeed.

Output structured markdown ending with a json proposed_actions block.
Each P1 finding (leaked secret, missing gitignore pattern, RLS gap)
becomes an ops action assigned to Tia. Title must start with 'Fix',
'Audit', or 'Rotate' so the classifier puts it in the Ops bucket.

CRITICAL OUTPUT INSTRUCTION: Do NOT use the Write tool. Output the
markdown directly to stdout. The bash wrapper saves your stdout to
outputs/security/security-agent-$DATE.md." \
"$OUTPUTS/security/security-agent-$DATE.md" \
"Read(.gitignore),Read(.claudeignore),Read(db/policies.sql),Read(db/schema.sql),Bash(grep),Bash(git log),Bash(git ls-files),Bash(curl)" \
"$MODEL_SONNET"

log "Phase 0 complete."
